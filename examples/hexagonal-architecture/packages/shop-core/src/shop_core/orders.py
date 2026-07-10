"""The orders domain: placing, cancelling, refunding, and exporting orders."""

import csv
import io
import json
from dataclasses import dataclass, field
from uuid import uuid4

from pymediate import Handler, Request

from shop_domain.orders import LineItem, Order, OrderStatus
from shop_domain.payments import Refund, RefundMethod
from shop_ports.customers import CustomerRepository
from shop_ports.notifications import Mailer
from shop_ports.orders import OrderRepository
from shop_ports.payments import PaymentGateway
from shop_ports.storage import FileStorage

from .errors import CustomerNotFoundError, InvalidOrderStateError, OrderNotFoundError


@dataclass
class PlaceOrder(Request[Order]):
    """Place an order for a customer; responds with the created Order."""

    customer_id: str
    items: list[LineItem] = field(default_factory=list)


class PlaceOrderHandler(Handler[PlaceOrder]):
    """Creates orders for existing customers."""

    def __init__(self, orders: OrderRepository, customers: CustomerRepository) -> None:
        self._orders = orders
        self._customers = customers

    def __call__(self, request: PlaceOrder) -> Order:
        if self._customers.get(request.customer_id) is None:
            raise CustomerNotFoundError(request.customer_id)
        order = Order(order_id=uuid4().hex, customer_id=request.customer_id, items=request.items)
        self._orders.add(order)
        return order


@dataclass
class CancelOrder(Request[Order]):
    """Cancel a placed order; responds with the updated Order."""

    order_id: str


class CancelOrderHandler(Handler[CancelOrder]):
    """Cancels orders that are still in the placed state."""

    def __init__(self, orders: OrderRepository) -> None:
        self._orders = orders

    def __call__(self, request: CancelOrder) -> Order:
        order = self._orders.get(request.order_id)
        if order is None:
            raise OrderNotFoundError(request.order_id)
        if order.status is not OrderStatus.PLACED:
            raise InvalidOrderStateError(order.order_id, order.status, "cancel")
        order.status = OrderStatus.CANCELLED
        self._orders.update(order)
        return order


@dataclass
class RefundOrder(Request[Refund]):
    """Refund a placed order; responds with the Refund record.

    Refunds go back to the original payment method through the payment gateway, or —
    when ``to_store_credit`` is set — onto the customer's store credit balance, which
    lives in the customers domain. Either way the customer gets a confirmation email.
    """

    order_id: str
    to_store_credit: bool = False


class RefundOrderHandler(Handler[RefundOrder]):
    """Refunds orders via the gateway or as store credit, and confirms by email.

    This is the use case that needs the most of the outside world: orders, customers,
    the payment provider, and the mailer. All four arrive as ports — the handler never
    constructs a collaborator, so nothing here imports another domain's machinery.
    """

    def __init__(
        self,
        orders: OrderRepository,
        customers: CustomerRepository,
        payments: PaymentGateway,
        mailer: Mailer,
    ) -> None:
        self._orders = orders
        self._customers = customers
        self._payments = payments
        self._mailer = mailer

    def __call__(self, request: RefundOrder) -> Refund:
        order = self._orders.get(request.order_id)
        if order is None:
            raise OrderNotFoundError(request.order_id)
        if order.status is not OrderStatus.PLACED:
            raise InvalidOrderStateError(order.order_id, order.status, "refund")

        amount = order.total_cents
        if request.to_store_credit:
            customer = self._customers.credit(order.customer_id, amount)
            method = RefundMethod.STORE_CREDIT
            reference = f"store-credit/{order.customer_id}"
        else:
            customer = self._customers.get(order.customer_id)
            method = RefundMethod.ORIGINAL_PAYMENT
            reference = self._payments.refund(order.order_id, amount)
        if customer is None:
            raise CustomerNotFoundError(order.customer_id)

        order.status = OrderStatus.REFUNDED
        self._orders.update(order)

        self._mailer.send(
            to=customer.email,
            subject=f"Your refund for order {order.order_id}",
            body=f"We refunded {amount} cents via {method.value} (reference {reference}).",
        )
        return Refund(
            order_id=order.order_id, amount_cents=amount, method=method, reference=reference
        )


@dataclass
class ExportResult:
    """Where an export landed, and how big it was."""

    url: str
    rows: int


@dataclass
class ExportOrders(Request[ExportResult]):
    """Export a customer's order history to a file; responds with its location."""

    customer_id: str
    fmt: str = "csv"


class ExportOrdersHandler(Handler[ExportOrders]):
    """Renders a customer's orders to a file in storage.

    The article's star ticket: because this is a handler behind the seam, running it
    from a background worker instead of the request cycle is a doorway change, not a
    rewrite.
    """

    def __init__(self, orders: OrderRepository, storage: FileStorage) -> None:
        self._orders = orders
        self._storage = storage

    def __call__(self, request: ExportOrders) -> ExportResult:
        orders = self._orders.for_customer(request.customer_id)
        rows = [
            {"order_id": o.order_id, "status": o.status.value, "total_cents": o.total_cents}
            for o in orders
        ]
        if request.fmt == "json":
            content = json.dumps(rows, indent=2).encode()
        else:
            buffer = io.StringIO()
            writer = csv.DictWriter(buffer, fieldnames=["order_id", "status", "total_cents"])
            writer.writeheader()
            writer.writerows(rows)
            content = buffer.getvalue().encode()
        name = f"orders-{request.customer_id}.{request.fmt}"
        url = self._storage.write(name, content)
        return ExportResult(url=url, rows=len(rows))
