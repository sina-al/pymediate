"""Test the safe public order-history projection directly."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime

from shop.application.orders.get_order_history import (
    GetOrderHistoryHandler,
    GetOrderHistoryRequest,
)
from shop.domain.events.base import AggregateType
from shop.ports.audit import DomainEventJournalReader, DomainEventRecord

from ..support import autospec


async def _records(*records: DomainEventRecord) -> AsyncIterator[DomainEventRecord]:
    for record in records:
        yield record


def _record(
    event_id: str,
    event_type: str,
    payload: dict[str, object],
    *,
    schema_version: int = 1,
) -> DomainEventRecord:
    return DomainEventRecord(
        event_id,
        event_type,
        schema_version,
        datetime(2026, 7, 16, tzinfo=UTC),
        AggregateType.ORDER,
        "42",
        payload,  # type: ignore[arg-type]
    )


async def test_order_history_allowlists_fields_and_omits_unknown_events() -> None:
    # Arrange
    journal = autospec(DomainEventJournalReader)
    placed = _record("00000000-0000-0000-0000-000000000001", "orders.order-placed", {})
    secret = _record(
        "00000000-0000-0000-0000-000000000002",
        "orders.internal-risk-score-calculated",
        {"risk_score": 99, "internal_note": "never expose this"},
    )
    future_placed = _record(
        "00000000-0000-0000-0000-000000000005",
        "orders.order-placed",
        {"renamed_field": "not understood by version one"},
        schema_version=2,
    )
    refunded = _record(
        "00000000-0000-0000-0000-000000000003",
        "orders.order-refunded",
        {"amount_pence": 500, "refunded_pence": 500, "status": "partially-refunded"},
    )
    cancelled = _record("00000000-0000-0000-0000-000000000004", "orders.order-cancelled", {})
    journal.stream_domain_events.return_value = _records(
        placed, secret, future_placed, refunded, cancelled
    )
    handle = GetOrderHistoryHandler(journal)

    # Act
    response = await handle(GetOrderHistoryRequest(42))

    # Assert
    assert [entry.kind for entry in response.entries] == ["placed", "refunded", "cancelled"]
    assert response.entries[1].amount_pence == 500
    assert response.entries[2].status == "cancelled"
    assert all(not hasattr(entry, "payload") for entry in response.entries)
    journal.stream_domain_events.assert_called_once_with(AggregateType.ORDER, "42")
