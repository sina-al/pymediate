"""Orders: what a customer buys, and the states an order moves through."""

from dataclasses import dataclass, field
from enum import StrEnum


class OrderStatus(StrEnum):
    """The lifecycle of an order."""

    PLACED = "placed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


@dataclass
class LineItem:
    """One line of an order."""

    sku: str
    quantity: int
    unit_price_cents: int


@dataclass
class Order:
    """A customer's order."""

    order_id: str
    customer_id: str
    items: list[LineItem] = field(default_factory=list)
    status: OrderStatus = OrderStatus.PLACED

    @property
    def total_cents(self) -> int:
        """The order total, in cents."""
        return sum(item.quantity * item.unit_price_cents for item in self.items)
