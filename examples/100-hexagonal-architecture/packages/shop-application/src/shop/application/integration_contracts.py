"""Typed integration events owned by the application boundary."""

from dataclasses import dataclass
from typing import ClassVar

from shop.ports.integration import JsonObject


@dataclass(frozen=True)
class OrderConfirmationRequestedV1:
    """Request confirmation delivery after an order has been committed."""

    order_id: int
    customer_id: int

    event_type: ClassVar[str] = "shop.orders.order-confirmation-requested"
    schema_version: ClassVar[int] = 1

    def payload(self) -> JsonObject:
        """Return the version-one wire payload."""
        return {"order_id": self.order_id, "customer_id": self.customer_id}


@dataclass(frozen=True)
class InvoiceRequestedV1:
    """Request invoice creation after an order has been committed."""

    order_id: int
    customer_id: int
    total_pence: int

    event_type: ClassVar[str] = "shop.invoices.invoice-requested"
    schema_version: ClassVar[int] = 1

    def payload(self) -> JsonObject:
        """Return the version-one wire payload."""
        return {
            "order_id": self.order_id,
            "customer_id": self.customer_id,
            "total_pence": self.total_pence,
        }


@dataclass(frozen=True)
class OrderExportRequestedV1:
    """Request generation of one customer's order export."""

    customer_id: int
    format: str

    event_type: ClassVar[str] = "shop.orders.order-export-requested"
    schema_version: ClassVar[int] = 1

    def payload(self) -> JsonObject:
        """Return the version-one wire payload."""
        return {"customer_id": self.customer_id, "format": self.format}
