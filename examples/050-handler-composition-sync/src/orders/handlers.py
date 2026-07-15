"""The handlers — and the one that composes the others.

``PlaceOrderHandler`` is the whole point of this example. It owns exactly one operation
(placing an order), yet placing an order *requires* reserving stock, charging a card, and
announcing the result. It does none of those itself and holds none of the other handlers.
It reaches them through the mediator: two ``send`` calls for the sub-requests and one
``publish`` for the announcement.

This is the synchronous mirror of ``050-handler-composition``. The difference is here: with
no event loop, the two sub-requests run **one after another** rather than concurrently. The
composition pattern — dispatching instead of holding — is identical.

Every handler appends to a shared ``journal`` so the ordering is visible in the demo and
asserted in the tests.
"""

from itertools import count

from pymediate.sync import EventHandler, RequestHandler

from .domain import (
    ChargePayment,
    Order,
    OrderPlaced,
    OutOfStockError,
    PaymentDeclinedError,
    PaymentGateway,
    PlaceOrder,
    Receipt,
    Reservation,
    ReserveStock,
    Sender,
    Warehouse,
)

# ---- The sub-operations: ordinary handlers, unaware they're being composed ----


class ReserveStockHandler(RequestHandler[ReserveStock]):
    """Reserve stock against the warehouse. Knows nothing about orders or payments."""

    def __init__(self, warehouse: Warehouse, journal: list[str]) -> None:
        self._warehouse = warehouse
        self._journal = journal

    def __call__(self, request: ReserveStock) -> Reservation:
        self._journal.append(f"reserve:start {request.sku}")
        available = self._warehouse.stock.get(request.sku, 0)
        if available < request.quantity:
            raise OutOfStockError(f"{request.sku}: wanted {request.quantity}, had {available}")
        self._warehouse.stock[request.sku] = available - request.quantity
        self._journal.append(f"reserve:done {request.sku}")
        return Reservation(request.sku, request.quantity)


class ChargePaymentHandler(RequestHandler[ChargePayment]):
    """Charge a card against the payment gateway. Knows nothing about orders or stock."""

    def __init__(self, gateway: PaymentGateway, journal: list[str]) -> None:
        self._gateway = gateway
        self._journal = journal

    def __call__(self, request: ChargePayment) -> Receipt:
        self._journal.append(f"charge:start {request.customer_id}")
        if request.customer_id in self._gateway.declined:
            raise PaymentDeclinedError(f"card declined for {request.customer_id}")
        receipt = Receipt(request.customer_id, request.amount_cents)
        self._gateway.charged.append(receipt)
        self._journal.append(f"charge:done {request.customer_id}")
        return receipt


# ---- The composing handler: orchestrates the others through the mediator ----


class PlaceOrderHandler(RequestHandler[PlaceOrder]):
    """Place an order by dispatching sub-requests — never by holding the other handlers.

    The revelation: a command has one owner, but it can orchestrate others *through the
    mediator*. This handler depends only on a ``Sender`` (the dispatch interface), so it can
    be constructed before the mediator it will dispatch into — see ``app.build_mediator``
    for how that cycle is closed. In the sync API the sub-requests run sequentially.
    """

    def __init__(self, sender: Sender, journal: list[str]) -> None:
        self._sender = sender
        self._journal = journal
        self._next_id = count(1)

    def __call__(self, request: PlaceOrder) -> Order:
        self._journal.append("place:start")
        # Same composition as the async twin, but sequential: no event loop to overlap on,
        # so the first send fully completes before the second begins.
        reservation = self._sender.send(ReserveStock(request.sku, request.quantity))
        receipt = self._sender.send(ChargePayment(request.customer_id, request.amount_cents))
        order = Order(next(self._next_id), reservation, receipt)
        # Announce the fact and move on. Subscribers react on their own; this handler
        # neither knows who listens nor waits on their work.
        self._sender.publish(OrderPlaced(order.order_id, request.customer_id))
        self._journal.append("place:done")
        return order


# ---- Subscribers: the "announce" side, each reacting independently ----


class OrderConfirmation(EventHandler[OrderPlaced]):
    """Email the customer. One of several reactions to a placed order."""

    def __init__(self, journal: list[str]) -> None:
        self._journal = journal

    def __call__(self, event: OrderPlaced) -> None:
        self._journal.append(f"email:sent {event.customer_id}")


class SalesAnalytics(EventHandler[OrderPlaced]):
    """Record the sale for reporting. Reacts to the same event, unaware of the emailer."""

    def __init__(self, journal: list[str]) -> None:
        self._journal = journal

    def __call__(self, event: OrderPlaced) -> None:
        self._journal.append(f"analytics:recorded {event.order_id}")
