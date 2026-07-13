"""The requests and handlers — and the one handler that composes the others.

`PlaceOrderHandler` is the point of the example. It needs to reserve stock *and* quote
shipping before it can save an order, but it never imports or holds `ReserveStockHandler`
or `QuoteShippingHandler`. It `send()`s a `ReserveStock` and a `QuoteShipping` through the
injected `Dispatcher`, and because those two are independent it runs them together with
`asyncio.gather` — the mediator resolves and runs each sub-handler, the orchestrator just
asks for results.
"""

import asyncio
from dataclasses import dataclass

from pymediate import Request, RequestHandler

from .dispatch import Dispatcher
from .domain import (
    Order,
    OrderStore,
    ShippingQuote,
    ShippingRates,
    StockReservation,
    Warehouse,
)

# ---- Requests: each declares the response type it resolves to ----


@dataclass
class ReserveStock(Request[StockReservation]):
    """Reserve stock for the items; responds with a StockReservation."""

    items: list[str]


@dataclass
class QuoteShipping(Request[ShippingQuote]):
    """Quote shipping for the items; responds with a ShippingQuote."""

    items: list[str]


@dataclass
class PlaceOrder(Request[Order]):
    """Place an order for the items; responds with the created Order."""

    items: list[str]


# ---- Leaf handlers: one operation each, holding only their own collaborator ----


class ReserveStockHandler(RequestHandler[ReserveStock]):
    """Reserves stock through the warehouse — knows nothing about orders or shipping."""

    def __init__(self, warehouse: Warehouse) -> None:
        self._warehouse = warehouse

    async def __call__(self, request: ReserveStock) -> StockReservation:
        return await self._warehouse.reserve(request.items)


class QuoteShippingHandler(RequestHandler[QuoteShipping]):
    """Quotes shipping through the rates service — knows nothing about orders or stock."""

    def __init__(self, rates: ShippingRates) -> None:
        self._rates = rates

    async def __call__(self, request: QuoteShipping) -> ShippingQuote:
        return await self._rates.quote(request.items)


# ---- The composing handler: orchestrates the two above, through the mediator ----


class PlaceOrderHandler(RequestHandler[PlaceOrder]):
    """Places an order by composing two sub-operations — reserve stock and quote shipping.

    It holds a `Dispatcher`, never the other handlers. The two sub-requests don't depend on
    each other, so `asyncio.gather` runs them concurrently; the order is saved only once
    both come back.
    """

    def __init__(self, dispatch: Dispatcher, store: OrderStore) -> None:
        self._dispatch = dispatch
        self._store = store

    async def __call__(self, request: PlaceOrder) -> Order:
        # Independent sub-requests, dispatched through the mediator and overlapped. Neither
        # handler is referenced here — the mediator routes each ReserveStock/QuoteShipping.
        reservation, quote = await asyncio.gather(
            self._dispatch.send(ReserveStock(items=request.items)),
            self._dispatch.send(QuoteShipping(items=request.items)),
        )
        return self._store.save(
            items=request.items,
            reservation_id=reservation.reservation_id,
            shipping_cost=quote.cost,
        )
