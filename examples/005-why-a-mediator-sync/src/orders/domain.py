"""The orders data and collaborators shared by both implementations.

`before/` uses one `OrderService` and `after/` uses one request handler per operation.
Both implementations operate on the same types. The collaborators are in-memory substitutes
for a database, payment provider, email service, warehouse, and audit log.
"""

from dataclasses import dataclass, field

# ---- Data ----


@dataclass
class Order:
    """An order on the books."""

    order_id: int
    customer_id: int
    items: list[str]
    status: str = "placed"


@dataclass
class ExportResult:
    """The outcome of exporting a customer's orders: where to download it, and how big."""

    url: str
    rows: int


class OutOfStockError(Exception):
    """Raised when an order asks for more than inventory can supply."""


class OrderNotFoundError(Exception):
    """Raised when an operation references an order id that doesn't exist."""


# ---- Collaborators: fakes standing in for real infrastructure ----


@dataclass
class OrderStore:
    """In-memory order storage (a stand-in for a database)."""

    orders: dict[int, Order] = field(default_factory=dict)
    next_id: int = 1

    def save(self, customer_id: int, items: list[str]) -> Order:
        """Persist a new order and return it."""
        order = Order(order_id=self.next_id, customer_id=customer_id, items=list(items))
        self.orders[order.order_id] = order
        self.next_id += 1
        return order

    def get(self, order_id: int) -> Order:
        """Fetch an order by id, or raise OrderNotFoundError."""
        order = self.orders.get(order_id)
        if order is None:
            raise OrderNotFoundError(f"No order with id {order_id}")
        return order


@dataclass
class PaymentGateway:
    """Charges and refunds cards (a stand-in for a payment provider)."""

    charges: list[tuple[int, int]] = field(default_factory=list)
    refunds: list[tuple[int, int]] = field(default_factory=list)

    def charge(self, order_id: int, amount: int) -> None:
        """Charge the customer for an order."""
        self.charges.append((order_id, amount))

    def refund(self, order_id: int, amount: int) -> None:
        """Refund a previous charge."""
        self.refunds.append((order_id, amount))


@dataclass
class Mailer:
    """Sends transactional email (a stand-in for an email service)."""

    sent: list[str] = field(default_factory=list)

    def send(self, to: str, subject: str) -> None:
        """Queue an email; we only keep the subject line for the demo."""
        self.sent.append(subject)


@dataclass
class InventoryService:
    """Tracks stock levels (a stand-in for a warehouse system)."""

    in_stock: bool = True

    def reserve(self, items: list[str]) -> None:
        """Reserve stock for an order, or raise OutOfStockError."""
        if not self.in_stock:
            raise OutOfStockError("insufficient stock")


@dataclass
class AuditLog:
    """An append-only record of what the application did."""

    entries: list[str] = field(default_factory=list)

    def record(self, action: str) -> None:
        """Append one action to the trail."""
        self.entries.append(action)
