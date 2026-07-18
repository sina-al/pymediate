"""Idempotent consumer-inbox contracts."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, runtime_checkable

from shop.ports.leases import LeaseToken


class InboxDisposition(StrEnum):
    """Result of atomically claiming an integration message for dispatch."""

    PROCESS = "process"
    PROCESSED = "processed"
    BUSY = "busy"


@dataclass(frozen=True, slots=True)
class InboxClaim:
    """An inbox decision, carrying ownership only when processing may begin."""

    disposition: InboxDisposition
    lease_token: LeaseToken | None = None

    def __post_init__(self) -> None:
        owns_lease = self.lease_token is not None
        if owns_lease != (self.disposition is InboxDisposition.PROCESS):
            raise ValueError("only a process inbox claim may carry a lease token")

    @classmethod
    def process(cls, lease_token: LeaseToken) -> "InboxClaim":
        """Allow dispatch under the supplied lease."""
        return cls(InboxDisposition.PROCESS, lease_token)

    @classmethod
    def processed(cls) -> "InboxClaim":
        """Report that the message was processed by an earlier delivery."""
        return cls(InboxDisposition.PROCESSED)

    @classmethod
    def busy(cls) -> "InboxClaim":
        """Report that another consumer still owns the processing lease."""
        return cls(InboxDisposition.BUSY)


@runtime_checkable
class MessageInbox(Protocol):
    """Deduplicate broker deliveries using expiring processing leases."""

    async def claim_inbox_message(self, message_id: str, lease_seconds: int) -> InboxClaim: ...
    async def renew_inbox_message(
        self, message_id: str, lease_token: LeaseToken, lease_seconds: int
    ) -> bool: ...
    async def complete_inbox_message(self, message_id: str, lease_token: LeaseToken) -> bool: ...
    async def release_inbox_message(self, message_id: str, lease_token: LeaseToken) -> bool: ...
