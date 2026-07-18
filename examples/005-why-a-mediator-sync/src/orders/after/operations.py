"""One request and one handler per order operation.

Each `Request` subclass declares its response type, which determines the return type of
`mediator.send(...)`. Each handler receives only the collaborators used by its operation.
Successful-request auditing is defined once in ``wiring.py``.

This is the synchronous mirror of `examples/005-why-a-mediator/`, built on ``pymediate.sync``.
"""

from dataclasses import dataclass

from pymediate.sync import Request, RequestHandler

from orders.domain import (
    ExportResult,
    InventoryService,
    Mailer,
    Order,
    OrderStore,
    PaymentGateway,
)

PRICE = 10  # flat price per item, for the demo


# ---- Requests: each declares the response type it resolves to ----


@dataclass
class PlaceOrder(Request[Order]):
    """Place an order for a customer; responds with the created Order."""

    customer_id: int
    items: list[str]


@dataclass
class CancelOrder(Request[Order]):
    """Cancel an order; responds with the updated Order."""

    order_id: int


@dataclass
class RefundOrder(Request[Order]):
    """Refund an order; responds with the updated Order."""

    order_id: int
    amount: int


@dataclass
class ExportOrders(Request[ExportResult]):
    """Export a customer's orders; responds with a download link and a row count."""

    customer_id: int
    fmt: str = "csv"


# ---- Handlers: exactly one per request, each holding only what it uses ----


class PlaceOrderHandler(RequestHandler[PlaceOrder]):
    """Places orders: reserves stock, saves, charges, and emails a confirmation."""

    def __init__(
        self,
        store: OrderStore,
        payments: PaymentGateway,
        mailer: Mailer,
        inventory: InventoryService,
    ) -> None:
        self._store = store
        self._payments = payments
        self._mailer = mailer
        self._inventory = inventory

    def __call__(self, request: PlaceOrder) -> Order:
        self._inventory.reserve(request.items)
        order = self._store.save(request.customer_id, request.items)
        self._payments.charge(order.order_id, PRICE * len(request.items))
        self._mailer.send(f"customer-{request.customer_id}", f"Order {order.order_id} placed")
        return order


class CancelOrderHandler(RequestHandler[CancelOrder]):
    """Cancels orders — and needs nothing but the store to do it."""

    def __init__(self, store: OrderStore) -> None:
        self._store = store

    def __call__(self, request: CancelOrder) -> Order:
        order = self._store.get(request.order_id)
        order.status = "cancelled"
        return order


class RefundOrderHandler(RequestHandler[RefundOrder]):
    """Refunds orders: the store and the payment gateway, and nothing else."""

    def __init__(self, store: OrderStore, payments: PaymentGateway) -> None:
        self._store = store
        self._payments = payments

    def __call__(self, request: RefundOrder) -> Order:
        order = self._store.get(request.order_id)
        self._payments.refund(request.order_id, request.amount)
        order.status = "refunded"
        return order


class ExportOrdersHandler(RequestHandler[ExportOrders]):
    """Exports a customer's orders; only the store is needed to read them."""

    def __init__(self, store: OrderStore) -> None:
        self._store = store

    def __call__(self, request: ExportOrders) -> ExportResult:
        rows = [o for o in self._store.orders.values() if o.customer_id == request.customer_id]
        return ExportResult(url=f"/exports/{request.customer_id}.{request.fmt}", rows=len(rows))
