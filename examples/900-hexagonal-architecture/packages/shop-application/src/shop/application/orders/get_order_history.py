"""Project the internal journal into a safe, order-specific history."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from pymediate import Request, RequestHandler

from shop.domain.events.base import AggregateType
from shop.domain.events.orders import OrderCancelledEvent, OrderPlacedEvent, OrderRefundedEvent
from shop.ports.audit import DomainEventJournalReader, DomainEventRecord

type OrderHistoryKind = Literal["placed", "refunded", "cancelled"]


@dataclass(frozen=True)
class OrderHistoryEntry:
    """One allowlisted order fact with no arbitrary journal payload."""

    event_id: str
    kind: OrderHistoryKind
    occurred_at: datetime
    amount_pence: int | None = None
    refunded_pence: int | None = None
    status: str | None = None


@dataclass(frozen=True)
class GetOrderHistoryResponse:
    """Return the public history entries known by this application version."""

    order_id: int
    entries: tuple[OrderHistoryEntry, ...]


@dataclass(frozen=True)
class GetOrderHistoryRequest(Request[GetOrderHistoryResponse]):
    """Request the safe history projection for one order."""

    order_id: int


class GetOrderHistoryHandler(RequestHandler[GetOrderHistoryRequest]):
    """Allowlist stable domain facts instead of exposing raw journal records."""

    def __init__(self, journal: DomainEventJournalReader) -> None:
        self._journal = journal

    async def __call__(self, request: GetOrderHistoryRequest) -> GetOrderHistoryResponse:
        entries = tuple(
            [
                entry
                async for record in self._journal.stream_domain_events(
                    AggregateType.ORDER, str(request.order_id)
                )
                if (entry := self._project(record)) is not None
            ]
        )
        return GetOrderHistoryResponse(request.order_id, entries)

    @staticmethod
    def _project(record: DomainEventRecord) -> OrderHistoryEntry | None:
        match (record.event_type, record.schema_version):
            case (OrderPlacedEvent.event_name, OrderPlacedEvent.schema_version):
                return OrderHistoryEntry(record.event_id, "placed", record.occurred_at)
            case (OrderRefundedEvent.event_name, OrderRefundedEvent.schema_version):
                return OrderHistoryEntry(
                    record.event_id,
                    "refunded",
                    record.occurred_at,
                    amount_pence=_integer(record, "amount_pence"),
                    refunded_pence=_integer(record, "refunded_pence"),
                    status=_string(record, "status"),
                )
            case (OrderCancelledEvent.event_name, OrderCancelledEvent.schema_version):
                return OrderHistoryEntry(
                    record.event_id, "cancelled", record.occurred_at, status="cancelled"
                )
            case _:
                return None


def _integer(record: DomainEventRecord, name: str) -> int | None:
    value = record.payload.get(name)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _string(record: DomainEventRecord, name: str) -> str | None:
    value = record.payload.get(name)
    return value if isinstance(value, str) else None
