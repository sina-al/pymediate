"""Validate invariants of the durable domain-event envelope."""

from datetime import UTC, datetime

import pytest

from shop.domain.events.base import AggregateType
from shop.domain.events.orders import OrderPlacedEvent
from shop.ports.audit import DomainEventRecord


def _record(**changes: object) -> DomainEventRecord:
    values = {
        "event_id": "00000000-0000-0000-0000-000000000001",
        "event_type": "shop.domain.events.orders.OrderPlacedEvent",
        "schema_version": 1,
        "occurred_at": datetime(2026, 7, 16, tzinfo=UTC),
        "aggregate_type": AggregateType.ORDER,
        "aggregate_id": "42",
        "payload": {"order_id": 42},
    }
    values.update(changes)
    return DomainEventRecord(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"event_id": "not-a-uuid"}, "event_id must be a UUID"),
        ({"event_type": " "}, "event_type must not be empty"),
        ({"schema_version": 0}, "schema_version must be a positive integer"),
        ({"occurred_at": datetime(2026, 7, 16)}, "occurred_at must include a UTC offset"),
        ({"aggregate_type": ""}, "aggregate identity must not be empty"),
        ({"aggregate_id": ""}, "aggregate identity must not be empty"),
        ({"aggregate_id": 42}, "aggregate identity must not be empty"),
        ({"payload": {"bad": object()}}, "domain_event.payload.bad is not JSON-compatible"),
    ],
)
def test_domain_event_record_rejects_invalid_envelopes(
    changes: dict[str, object], message: str
) -> None:
    # Arrange
    invalid_values = changes

    # Act
    with pytest.raises(ValueError, match=message) as raised:
        _record(**invalid_values)

    # Assert
    assert message in str(raised.value)


def test_record_is_derived_from_a_self_describing_domain_event() -> None:
    # Arrange
    event = OrderPlacedEvent(42, 7, 1_500)

    # Act
    record = DomainEventRecord.from_event(event)

    # Assert
    assert record.event_type == "orders.order-placed"
    assert record.aggregate_type is AggregateType.ORDER
    assert record.aggregate_id == "42"
    assert record.payload == {"order_id": 42, "customer_id": 7, "total_pence": 1_500}
