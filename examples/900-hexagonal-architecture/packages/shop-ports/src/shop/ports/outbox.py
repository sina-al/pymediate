"""Transactional outbox values and persistence contracts."""

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from shop.ports.integration import IntegrationMessage
from shop.ports.leases import LeaseToken


@dataclass(frozen=True)
class OutboxMessage:
    """Persist an integration envelope beside its transport-only trace carrier."""

    message: IntegrationMessage
    trace_context: dict[str, str]

    @property
    def message_id(self) -> str:
        """Return the durable message identity used by relay settlement."""
        return self.message.message_id


@dataclass(frozen=True, slots=True)
class OutboxClaim:
    """An unpublished message and the opaque token proving lease ownership."""

    message: OutboxMessage
    lease_token: LeaseToken

    @property
    def message_id(self) -> str:
        """Return the durable message identity used by relay settlement."""
        return self.message.message_id


@runtime_checkable
class OutboxWriter(Protocol):
    """Persist an event envelope inside the caller's existing transaction."""

    async def insert_outbox_message(self, outbox: OutboxMessage) -> None: ...


@runtime_checkable
class OutboxRelaySource(Protocol):
    """Lease unpublished outbox messages for a separate relay process."""

    async def claim_outbox_messages(
        self, limit: int, lease_seconds: int
    ) -> tuple[OutboxClaim, ...]: ...
    async def renew_outbox_message(
        self, message_id: str, lease_token: LeaseToken, lease_seconds: int
    ) -> bool: ...
    async def mark_outbox_message_published(
        self, message_id: str, lease_token: LeaseToken
    ) -> bool: ...
    async def release_outbox_message(self, message_id: str, lease_token: LeaseToken) -> bool: ...
