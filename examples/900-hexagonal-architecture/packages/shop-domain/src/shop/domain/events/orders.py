"""Business facts emitted by the orders domain."""

from dataclasses import dataclass
from typing import ClassVar

from shop.domain.events.base import AggregateRef, AggregateType, EventPayload


@dataclass(frozen=True)
class OrderPlacedEvent:
    """Record that an order was successfully placed."""

    order_id: int
    customer_id: int
    total_pence: int

    event_name: ClassVar[str] = "orders.order-placed"
    schema_version: ClassVar[int] = 1

    @property
    def aggregate(self) -> AggregateRef:
        return AggregateRef(AggregateType.ORDER, str(self.order_id))

    def payload(self) -> EventPayload:
        """Return the durable primitive payload for this event."""
        return {
            "order_id": self.order_id,
            "customer_id": self.customer_id,
            "total_pence": self.total_pence,
        }


@dataclass(frozen=True)
class OrderExportRequestedEvent:
    """Record that an order-history export was accepted for background work."""

    customer_id: int
    format: str

    event_name: ClassVar[str] = "orders.export-requested"
    schema_version: ClassVar[int] = 1

    @property
    def aggregate(self) -> AggregateRef:
        return AggregateRef(AggregateType.CUSTOMER, str(self.customer_id))

    def payload(self) -> EventPayload:
        """Return the durable primitive payload for this event."""
        return {"customer_id": self.customer_id, "format": self.format}


@dataclass(frozen=True)
class OrderCancelledEvent:
    """Record that an order reached its cancelled terminal state."""

    order_id: int
    customer_id: int
    total_pence: int

    event_name: ClassVar[str] = "orders.order-cancelled"
    schema_version: ClassVar[int] = 1

    @property
    def aggregate(self) -> AggregateRef:
        return AggregateRef(AggregateType.ORDER, str(self.order_id))

    def payload(self) -> EventPayload:
        """Return the durable primitive payload for this event."""
        return {
            "order_id": self.order_id,
            "customer_id": self.customer_id,
            "total_pence": self.total_pence,
        }


@dataclass(frozen=True)
class OrderRefundedEvent:
    """Record a partial or complete refund in the Shop's committed order state."""

    order_id: int
    customer_id: int
    amount_pence: int
    refunded_pence: int
    status: str

    event_name: ClassVar[str] = "orders.order-refunded"
    schema_version: ClassVar[int] = 1

    @property
    def aggregate(self) -> AggregateRef:
        return AggregateRef(AggregateType.ORDER, str(self.order_id))

    def payload(self) -> EventPayload:
        """Return the durable primitive payload for this event."""
        return {
            "order_id": self.order_id,
            "customer_id": self.customer_id,
            "amount_pence": self.amount_pence,
            "refunded_pence": self.refunded_pence,
            "status": self.status,
        }
