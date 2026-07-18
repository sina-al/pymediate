"""Business facts emitted by the invoices domain."""

from dataclasses import dataclass
from typing import ClassVar

from shop.domain.events.base import AggregateRef, AggregateType, EventPayload


@dataclass(frozen=True)
class InvoiceCreatedEvent:
    """Record that an invoice document and record were created."""

    invoice_id: int
    order_id: int
    customer_id: int
    total_pence: int
    document_url: str

    event_name: ClassVar[str] = "invoices.invoice-created"
    schema_version: ClassVar[int] = 1

    @property
    def aggregate(self) -> AggregateRef:
        return AggregateRef(AggregateType.INVOICE, str(self.invoice_id))

    def payload(self) -> EventPayload:
        """Return the durable primitive payload for this event."""
        return {
            "invoice_id": self.invoice_id,
            "order_id": self.order_id,
            "customer_id": self.customer_id,
            "total_pence": self.total_pence,
            "document_url": self.document_url,
        }
