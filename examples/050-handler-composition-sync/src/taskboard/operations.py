"""The requests and handlers — and the one handler that composes the others.

`PlaceOrderHandler` is the point of the example. It needs to reserve stock *and* quote
shipping before it can save an order, but it never imports or holds `ReserveStockHandler`
or `QuoteShippingHandler`. It `send()`s a `ReserveStock` and a `QuoteShipping` through the
injected `Dispatcher`; the mediator resolves and runs each sub-handler.

This is the synchronous mirror of `examples/050-handler-composition/operations.py`. The one
real difference: with no event loop the two sub-requests run **sequentially** — plain
`send()` calls instead of `asyncio.gather`. The composition shape is identical.
"""

from dataclasses import dataclass

from pymediate.sync import Request, RequestHandler

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

    def __call__(self, request: ReserveStock) -> StockReservation:
        return self._warehouse.reserve(request.items)


class QuoteShippingHandler(RequestHandler[QuoteShipping]):
    """Quotes shipping through the rates service — knows nothing about orders or stock."""

    def __init__(self, rates: ShippingRates) -> None:
        self._rates = rates

    def __call__(self, request: QuoteShipping) -> ShippingQuote:
        return self._rates.quote(request.items)


# ---- The composing handler: orchestrates the two above, through the mediator ----


class PlaceOrderHandler(RequestHandler[PlaceOrder]):
    """Places an order by composing two sub-operations — reserve stock and quote shipping.

    It holds a `Dispatcher`, never the other handlers. Sync has no concurrency, so the two
    sub-requests run one after another; the order is saved once both return.
    """

    def __init__(self, dispatch: Dispatcher, store: OrderStore) -> None:
        self._dispatch = dispatch
        self._store = store

    def __call__(self, request: PlaceOrder) -> Order:
        # Two sub-requests, dispatched through the mediator, one after another. Neither
        # handler is referenced here — the mediator routes each ReserveStock/QuoteShipping.
        reservation = self._dispatch.send(ReserveStock(items=request.items))
        quote = self._dispatch.send(QuoteShipping(items=request.items))
        return self._store.save(
            items=request.items,
            reservation_id=reservation.reservation_id,
            shipping_cost=quote.cost,
        )
