"""Portable queue publication, delivery, and settlement contracts."""

from typing import Protocol, runtime_checkable

from shop.ports.integration import IntegrationMessage
from shop.ports.outbox import OutboxMessage


class DeliveryLockLostError(RuntimeError):
    """Raised when a stale broker delivery no longer owns its message lock."""


@runtime_checkable
class MessagePublisher(Protocol):
    """Publish one committed outbox message to the selected broker."""

    async def publish(self, outbox: OutboxMessage) -> None: ...


@runtime_checkable
class MessageDelivery(Protocol):
    """One locked broker delivery with portable settlement operations."""

    @property
    def message(self) -> IntegrationMessage: ...

    @property
    def trace_context(self) -> dict[str, str]: ...

    async def complete(self) -> None: ...
    async def abandon(self) -> None: ...
    async def renew(self) -> None: ...


@runtime_checkable
class MessageConsumer(Protocol):
    """Receive locked integration messages from a competing-consumer queue."""

    async def receive(self) -> MessageDelivery | None: ...
