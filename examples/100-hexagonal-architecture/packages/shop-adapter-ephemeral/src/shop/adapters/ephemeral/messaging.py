"""Process-local queue adapter with visibility and dead-letter semantics."""

import asyncio
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from shop.ports.broker import (
    DeliveryLockLostError,
    MessageConsumer,
    MessageDelivery,
    MessagePublisher,
)
from shop.ports.integration import IntegrationMessage, deserialize_message, serialize_message
from shop.ports.outbox import OutboxMessage


@dataclass
class _QueuedMessage:
    outbox: OutboxMessage
    delivery_count: int = 0
    visible_at: datetime | None = None
    delivery_token: UUID | None = None


class _EphemeralDelivery(MessageDelivery):
    def __init__(
        self, broker: "EphemeralMessageBroker", queued: _QueuedMessage, token: UUID
    ) -> None:
        self._broker = broker
        self._queued = queued
        self._token = token

    @property
    def message(self) -> IntegrationMessage:
        return self._queued.outbox.message

    @property
    def trace_context(self) -> dict[str, str]:
        return self._queued.outbox.trace_context

    @property
    def delivery_count(self) -> int:
        return self._queued.delivery_count

    async def complete(self) -> None:
        await self._broker._complete(self._queued, self._token)

    async def abandon(self) -> None:
        await self._broker._abandon(self._queued, self._token)

    async def renew(self) -> None:
        await self._broker._renew(self._queued, self._token)


class EphemeralMessageBroker(MessagePublisher, MessageConsumer):
    """Provide deterministic at-least-once delivery without an external service."""

    def __init__(self, visibility_seconds: int = 120, max_delivery_count: int = 5) -> None:
        self._visibility_seconds = visibility_seconds
        self._max_delivery_count = max_delivery_count
        self._messages: deque[_QueuedMessage] = deque()
        self._dead_letters: list[IntegrationMessage] = []
        self._lock = asyncio.Lock()

    async def publish(self, outbox: OutboxMessage) -> None:
        message = deserialize_message(serialize_message(outbox.message))
        async with self._lock:
            self._messages.append(
                _QueuedMessage(OutboxMessage(message, dict(outbox.trace_context)))
            )

    async def receive(self) -> MessageDelivery | None:
        async with self._lock:
            now = datetime.now(UTC)
            for queued in tuple(self._messages):
                if queued.visible_at is not None and queued.visible_at > now:
                    continue
                if queued.delivery_count >= self._max_delivery_count:
                    self._messages.remove(queued)
                    self._dead_letters.append(queued.outbox.message)
                    continue
                queued.delivery_count += 1
                queued.visible_at = now + timedelta(seconds=self._visibility_seconds)
                queued.delivery_token = uuid4()
                return _EphemeralDelivery(self, queued, queued.delivery_token)
        return None

    async def _complete(self, queued: _QueuedMessage, token: UUID) -> None:
        async with self._lock:
            self._require_current_delivery(queued, token)
            self._messages.remove(queued)

    async def _abandon(self, queued: _QueuedMessage, token: UUID) -> None:
        async with self._lock:
            self._require_current_delivery(queued, token)
            if queued.delivery_count >= self._max_delivery_count:
                self._messages.remove(queued)
                self._dead_letters.append(queued.outbox.message)
            else:
                queued.visible_at = datetime.now(UTC)
                queued.delivery_token = None

    async def _renew(self, queued: _QueuedMessage, token: UUID) -> None:
        async with self._lock:
            self._require_current_delivery(queued, token)
            queued.visible_at = datetime.now(UTC) + timedelta(seconds=self._visibility_seconds)

    def _require_current_delivery(self, queued: _QueuedMessage, token: UUID) -> None:
        if queued not in self._messages or queued.delivery_token != token:
            raise DeliveryLockLostError("ephemeral broker delivery lock is no longer owned")

    @property
    def dead_letters(self) -> tuple[IntegrationMessage, ...]:
        """Return poison messages moved aside after repeated delivery failures."""
        return tuple(self._dead_letters)
