"""Verify the local broker mirrors retry and DLQ behavior."""

from datetime import UTC, datetime

import pytest

from shop.adapters.ephemeral import EphemeralMessageBroker
from shop.ports.broker import DeliveryLockLostError, MessageDelivery
from shop.ports.integration import IntegrationMessage, JsonObject, JsonValue
from shop.ports.outbox import OutboxMessage


async def test_abandoned_message_retries_then_moves_to_dead_letter_queue() -> None:
    # Arrange
    broker = EphemeralMessageBroker(max_delivery_count=2)
    message = IntegrationMessage(
        "12345678-1234-5678-1234-567812345678",
        "example.Event",
        1,
        datetime.now(UTC),
        {},
    )
    await broker.publish(OutboxMessage(message, {}))

    # Act
    first = await require_delivery(broker)
    await first.abandon()
    second = await require_delivery(broker)
    await second.abandon()
    remaining = await broker.receive()

    # Assert
    assert remaining is None
    assert broker.dead_letters == (message,)


async def test_publish_crosses_the_same_serialization_boundary_as_cloud_brokers() -> None:
    # Arrange
    broker = EphemeralMessageBroker()
    items: list[JsonValue] = ["book"]
    payload: JsonObject = {"items": items}
    message = IntegrationMessage(
        "12345678-1234-5678-1234-567812345678",
        "example.Event",
        1,
        datetime.now(UTC),
        payload,
    )
    await broker.publish(OutboxMessage(message, {"traceparent": "original"}))

    # Act
    items.append("mug")
    delivery = await require_delivery(broker)

    # Assert
    assert delivery.message.payload == {"items": ["book"]}
    assert delivery.trace_context == {"traceparent": "original"}


async def test_repeated_visibility_expiry_counts_toward_dead_lettering() -> None:
    # Arrange
    broker = EphemeralMessageBroker(visibility_seconds=0, max_delivery_count=2)
    original = IntegrationMessage(
        "12345678-1234-5678-1234-567812345678",
        "example.Event",
        1,
        datetime.now(UTC),
        {},
    )
    await broker.publish(OutboxMessage(original, {}))

    # Act
    first = await require_delivery(broker)
    second = await require_delivery(broker)
    remaining = await broker.receive()

    # Assert
    assert first is not second
    assert remaining is None
    assert broker.dead_letters == (original,)


async def test_stale_delivery_handle_cannot_settle_a_newer_lock() -> None:
    # Arrange
    broker = EphemeralMessageBroker(visibility_seconds=0, max_delivery_count=3)
    original = IntegrationMessage(
        "12345678-1234-5678-1234-567812345678",
        "example.Event",
        1,
        datetime.now(UTC),
        {},
    )
    await broker.publish(OutboxMessage(original, {}))
    stale = await require_delivery(broker)
    current = await require_delivery(broker)

    # Act
    with pytest.raises(DeliveryLockLostError, match="no longer owned"):
        await stale.renew()
    with pytest.raises(DeliveryLockLostError, match="no longer owned"):
        await stale.complete()
    await current.abandon()
    redelivery = await require_delivery(broker)

    # Assert
    assert redelivery.message == original
    assert broker.dead_letters == ()


async def require_delivery(broker: EphemeralMessageBroker) -> MessageDelivery:
    """Receive one delivery or fail a focused broker test."""
    delivery = await broker.receive()
    assert delivery is not None
    return delivery
