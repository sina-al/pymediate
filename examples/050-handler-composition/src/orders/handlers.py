"""The handlers — and the one that composes the others.

``PlaceOrderHandler`` is the whole point of this example. It owns exactly one operation
(placing an order), yet placing an order *requires* reserving stock, charging a card, and
announcing the result. It does none of those itself and holds none of the other handlers.
It reaches them through the mediator: two ``send`` calls for the sub-requests and one
``publish`` for the announcement. Because reserving stock and charging a card don't depend
on each other, it runs them at the same time with ``asyncio.gather``.

Every handler appends to a shared ``journal`` so the ordering — including the overlap of
the two concurrent sub-requests — is visible in the demo and asserted in the tests.
"""

import asyncio
from itertools import count

from pymediate import EventHandler, RequestHandler

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

    async def __call__(self, request: ReserveStock) -> Reservation:
        self._journal.append(f"reserve:start {request.sku}")
        await asyncio.sleep(0)  # stand-in for awaiting a real inventory service
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

    async def __call__(self, request: ChargePayment) -> Receipt:
        self._journal.append(f"charge:start {request.customer_id}")
        await asyncio.sleep(0)  # stand-in for awaiting a real payment provider
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
    mediator*, including in parallel. This handler depends only on a ``Sender`` (the
    dispatch interface), so it can be constructed before the mediator it will dispatch
    into — see ``app.build_mediator`` for how that cycle is closed.
    """

    def __init__(self, sender: Sender, journal: list[str]) -> None:
        self._sender = sender
        self._journal = journal
        self._next_id = count(1)

    async def __call__(self, request: PlaceOrder) -> Order:
        self._journal.append("place:start")
        # Reserving stock and charging the card are independent — run them concurrently.
        # gather awaits both and returns their results in argument order.
        reservation, receipt = await asyncio.gather(
            self._sender.send(ReserveStock(request.sku, request.quantity)),
            self._sender.send(ChargePayment(request.customer_id, request.amount_cents)),
        )
        order = Order(next(self._next_id), reservation, receipt)
        # Announce the fact and move on. Subscribers react on their own; this handler
        # neither knows who listens nor waits on their work.
        await self._sender.publish(OrderPlaced(order.order_id, request.customer_id))
        self._journal.append("place:done")
        return order


# ---- Subscribers: the "announce" side, each reacting independently ----


class OrderConfirmation(EventHandler[OrderPlaced]):
    """Email the customer. One of several reactions to a placed order."""

    def __init__(self, journal: list[str]) -> None:
        self._journal = journal

    async def __call__(self, event: OrderPlaced) -> None:
        self._journal.append(f"email:sent {event.customer_id}")


class SalesAnalytics(EventHandler[OrderPlaced]):
    """Record the sale for reporting. Reacts to the same event, unaware of the emailer."""

    def __init__(self, journal: list[str]) -> None:
        self._journal = journal

    async def __call__(self, event: OrderPlaced) -> None:
        self._journal.append(f"analytics:recorded {event.order_id}")
