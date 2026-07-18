"""Business facts emitted by the statements domain."""

from dataclasses import dataclass
from typing import ClassVar

from shop.domain.events.base import AggregateRef, AggregateType, EventPayload


@dataclass(frozen=True)
class MonthlyStatementCreatedEvent:
    """Record that a customer's monthly statement was created."""

    statement_id: int
    customer_id: int
    year: int
    month: int
    currency: str
    order_count: int
    total_minor: int
    document_url: str

    event_name: ClassVar[str] = "statements.monthly-statement-created"
    schema_version: ClassVar[int] = 1

    @property
    def aggregate(self) -> AggregateRef:
        return AggregateRef(AggregateType.STATEMENT, str(self.statement_id))

    def payload(self) -> EventPayload:
        """Return the durable primitive payload for this event."""
        return {
            "statement_id": self.statement_id,
            "customer_id": self.customer_id,
            "year": self.year,
            "month": self.month,
            "currency": self.currency,
            "order_count": self.order_count,
            "total_minor": self.total_minor,
            "document_url": self.document_url,
        }
