"""What the application needs from the audit trail."""

from typing import Protocol


class AuditLog(Protocol):
    """A destination for one audit event per dispatched request."""

    def record(self, event: str) -> None:
        """Record one audit event."""
        ...
