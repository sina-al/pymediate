"""Service ports as recording stubs: gateway, mailer, storage, audit, job queue.

Each stub records what it was asked to do, which is exactly what both a test and a
demo need. The `memory` compose variant runs on these; the Postgres and Neo4j
variants reuse them for everything that isn't persistence.
"""

import logging
import queue
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

logger = logging.getLogger("shop")


@dataclass
class RecordingPaymentGateway:
    """PaymentGateway stub: records refunds and hands back a reference."""

    refunds: list[tuple[str, int]] = field(default_factory=list)

    def refund(self, order_id: str, amount_cents: int) -> str:
        self.refunds.append((order_id, amount_cents))
        reference = f"refund/{uuid4().hex[:8]}"
        logger.info("payment gateway: refunded %s cents for order %s", amount_cents, order_id)
        return reference


@dataclass
class RecordingMailer:
    """Mailer stub: keeps an outbox instead of sending."""

    outbox: list[tuple[str, str, str]] = field(default_factory=list)

    def send(self, to: str, subject: str, body: str) -> None:
        self.outbox.append((to, subject, body))
        logger.info("mail to %s: %s", to, subject)


class LocalFileStorage:
    """FileStorage on the local filesystem, returning file:// URLs."""

    def __init__(self, directory: str | Path) -> None:
        self._directory = Path(directory)

    def write(self, name: str, content: bytes) -> str:
        self._directory.mkdir(parents=True, exist_ok=True)
        path = self._directory / name
        path.write_bytes(content)
        return path.resolve().as_uri()


@dataclass
class LoggingAuditLog:
    """AuditLog that keeps events in a list and logs them."""

    events: list[str] = field(default_factory=list)

    def record(self, event: str) -> None:
        self.events.append(event)
        logger.info("audit: %s", event)


class MemoryJobQueue:
    """JobQueue on queue.Queue — jobs stay in this process.

    The memory variant runs its export worker as a background thread in the same
    process, so an in-process queue is the honest implementation. The Postgres and
    Neo4j variants swap this for Redis without the core noticing.
    """

    def __init__(self) -> None:
        self.jobs: queue.Queue[dict[str, Any]] = queue.Queue()

    def enqueue(self, job: dict[str, Any]) -> None:
        self.jobs.put(job)
