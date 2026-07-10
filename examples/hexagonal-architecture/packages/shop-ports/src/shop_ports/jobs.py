"""What the application needs in order to defer work."""

from typing import Any, Protocol


class JobQueue(Protocol):
    """A queue for jobs that should run outside the request cycle.

    Payloads are JSON-serializable dicts, so a job can cross a process boundary
    (Redis) or stay in-process (a plain queue) without either side knowing which.
    """

    def enqueue(self, job: dict[str, Any]) -> None:
        """Add one job to the queue."""
        ...
