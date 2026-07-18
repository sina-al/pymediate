"""The projection worker: the read model's only writer, driven by the outbox.

This is the piece that keeps the read side correct. A command handler never touches DuckDB;
it writes SQLite and returns. The projector, running separately, reads the outbox in order and
materialises DuckDB in checkpointed batches. That decoupling is the whole point — the second
store's write is no longer inside the command's failure boundary.

The unit of work and the loop are deliberately split:

- ``Projector.drain`` is a plain synchronous method that catches the read model up to the
  outbox and returns how many events it applied. Tests call it directly, so they never depend
  on timing.
- ``ProjectionWorker`` wraps ``drain`` in an ``asyncio`` loop that wakes on a nudge (see
  ``handlers.WakeProjector``) and otherwise polls, so a lost nudge only ever costs latency.
"""

import asyncio
import sqlite3
from pathlib import Path

from .read_store import ProjectionTarget
from .write_store import read_outbox


class Projector:
    """Reads the outbox through its own connection and applies it to a ``ProjectionTarget``."""

    def __init__(
        self, outbox_database: Path | str, target: ProjectionTarget, *, batch_size: int = 500
    ) -> None:
        self._conn = sqlite3.connect(outbox_database)
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._target = target
        self._batch_size = batch_size

    def drain(self) -> int:
        """Apply every outbox event past the checkpoint, one batch per transaction.

        Returns the total number of events applied. Each ``apply_batch`` is a single DuckDB
        transaction of up to ``batch_size`` events, so a burst of commands collapses into a
        few physical read-model writes rather than one per command.
        """
        applied = 0
        while True:
            after = self._target.checkpoint()
            events = read_outbox(self._conn, after, self._batch_size)
            if not events:
                return applied
            self._target.apply_batch(events)
            applied += len(events)

    def close(self) -> None:
        """Close the outbox read connection."""
        self._conn.close()


class ProjectionWorker:
    """Runs a ``Projector`` in a background loop: wake on a nudge, else poll.

    The worker does blocking SQLite/DuckDB I/O directly on the event loop, which is fine for a
    single-writer demo. A production worker would offload that I/O to a thread (or use async
    drivers) so it never stalls other tasks.
    """

    def __init__(self, projector: Projector, *, poll_interval: float = 0.2) -> None:
        self._projector = projector
        self._poll_interval = poll_interval
        self._wake = asyncio.Event()
        self._running = False

    def wake(self) -> None:
        """Signal that new outbox rows are waiting (a latency optimisation over polling)."""
        self._wake.set()

    async def run(self) -> None:
        """Drain, then wait for a nudge or the poll timeout, until ``stop`` is called."""
        self._running = True
        while self._running:
            self._projector.drain()
            try:
                await asyncio.wait_for(self._wake.wait(), timeout=self._poll_interval)
            except TimeoutError:
                pass  # the periodic poll: nudges can be lost, the outbox never is
            self._wake.clear()

    async def stop(self) -> None:
        """Ask the loop to finish after its current iteration."""
        self._running = False
        self._wake.set()


async def wait_until_caught_up(
    target: ProjectionTarget, position: int, *, timeout: float = 2.0, poll: float = 0.01
) -> None:
    """Await until the read model's checkpoint reaches ``position`` — explicit read-your-writes.

    The read side is eventually consistent: a command commits to SQLite and returns before the
    projector has materialised DuckDB. A caller that needs to read its own write waits until
    the checkpoint has passed the outbox position the command handed back.
    """
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while target.checkpoint() < position:
        if loop.time() >= deadline:
            raise TimeoutError(
                f"read model did not reach outbox position {position} within {timeout}s"
            )
        await asyncio.sleep(poll)
