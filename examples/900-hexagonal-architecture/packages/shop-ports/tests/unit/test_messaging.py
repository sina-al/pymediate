"""Test the transport-independent integration-message contract."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone
from typing import ClassVar, cast
from uuid import UUID

import pytest

from shop.ports.integration import (
    IntegrationMessage,
    JsonObject,
    deserialize_message,
    serialize_message,
)


@dataclass(frozen=True)
class ExampleEvent:
    order_id: int

    event_type: ClassVar[str] = "shop.example.requested"
    schema_version: ClassVar[int] = 1

    def payload(self) -> JsonObject:
        return {"order_id": self.order_id}


def message(**changes: object) -> IntegrationMessage:
    values = {
        "message_id": "12345678-1234-5678-1234-567812345678",
        "event_type": "shop.domain.events.orders.OrderPlacedEvent",
        "schema_version": 1,
        "occurred_at": datetime(2026, 7, 15, tzinfo=UTC),
        "payload": cast("JsonObject", {"order_id": 1, "nested": [True, None]}),
    }
    values.update(changes)
    return IntegrationMessage(**values)  # type: ignore[arg-type]


def test_message_round_trips_as_canonical_utc_json() -> None:
    # Arrange
    original = message()

    # Act
    encoded = serialize_message(original)

    # Assert
    assert deserialize_message(encoded) == original
    assert encoded == (
        '{"event_type":"shop.domain.events.orders.OrderPlacedEvent",'
        '"message_id":"12345678-1234-5678-1234-567812345678",'
        '"occurred_at":"2026-07-15T00:00:00+00:00",'
        '"payload":{"nested":[true,null],"order_id":1},"schema_version":1}'
    )


@pytest.mark.parametrize("body", ["[]", "{}", '{"message_id":3}', "not-json"])
def test_deserializer_rejects_invalid_envelope_shapes(body: str) -> None:
    # Arrange
    invalid_body = body

    # Act
    with pytest.raises((ValueError, TypeError)) as raised:
        deserialize_message(invalid_body)

    # Assert
    assert isinstance(raised.value, ValueError | TypeError)


@pytest.mark.parametrize(
    ("changes", "problem"),
    [
        ({"message_id": "not-a-uuid"}, "must be a UUID"),
        ({"event_type": "  "}, "must not be empty"),
        ({"schema_version": 0}, "must be a positive integer"),
        ({"occurred_at": datetime(2026, 7, 15)}, "must be in UTC"),
        ({"payload": cast("JsonObject", {"bad": object()})}, "not JSON-compatible"),
    ],
)
def test_message_rejects_invalid_contract_values(changes: dict[str, object], problem: str) -> None:
    # Arrange
    invalid_values = changes

    # Act
    with pytest.raises(ValueError, match=problem) as raised:
        message(**invalid_values)

    # Assert
    assert problem in str(raised.value)


def test_message_is_created_from_one_self_describing_integration_event() -> None:
    # Arrange
    event = ExampleEvent(order_id=42)

    # Act
    result = IntegrationMessage.from_event(event)

    # Assert
    UUID(result.message_id)
    assert result.event_type == ExampleEvent.event_type
    assert result.schema_version == ExampleEvent.schema_version
    assert result.occurred_at.tzinfo is UTC
    assert result.payload == {"order_id": 42}


@pytest.mark.parametrize(
    "value",
    [float("nan"), float("inf"), float("-inf")],
)
def test_message_rejects_non_finite_json_numbers(value: float) -> None:
    # Arrange
    payload = cast("JsonObject", {"value": value})

    # Act
    with pytest.raises(ValueError, match="not JSON-compatible") as raised:
        message(payload=payload)

    # Assert
    assert "not JSON-compatible" in str(raised.value)


def test_message_accepts_a_finite_json_number() -> None:
    # Arrange
    original = message(payload={"value": 1.5})

    # Act
    encoded = serialize_message(original)

    # Assert
    assert deserialize_message(encoded).payload == {"value": 1.5}


def test_message_requires_utc_rather_than_an_arbitrary_aware_timestamp() -> None:
    # Arrange
    non_utc = datetime(2026, 7, 15, tzinfo=timezone(timedelta(hours=1)))

    # Act
    with pytest.raises(ValueError, match="must be in UTC") as raised:
        message(occurred_at=non_utc)

    # Assert
    assert "must be in UTC" in str(raised.value)


@pytest.mark.parametrize(
    "body",
    [
        '{"message_id":"12345678-1234-5678-1234-567812345678",'
        '"event_type":"event","schema_version":true,'
        '"occurred_at":"2026-07-15T00:00:00+00:00","payload":{}}',
        '{"message_id":"12345678-1234-5678-1234-567812345678",'
        '"event_type":"event","schema_version":1,'
        '"occurred_at":"invalid","payload":{}}',
        '{"message_id":"12345678-1234-5678-1234-567812345678",'
        '"event_type":"event","schema_version":1,'
        '"occurred_at":"2026-07-15T00:00:00+00:00","payload":{},"extra":1}',
        '{"message_id":"12345678-1234-5678-1234-567812345678",'
        '"event_type":"event","schema_version":1,'
        '"occurred_at":"2026-07-15T00:00:00+00:00","payload":{"value":NaN}}',
    ],
)
def test_deserializer_rejects_wrong_types_timestamps_and_extra_fields(body: str) -> None:
    # Arrange
    invalid_body = body

    # Act
    with pytest.raises(ValueError) as raised:
        deserialize_message(invalid_body)

    # Assert
    assert str(raised.value)
