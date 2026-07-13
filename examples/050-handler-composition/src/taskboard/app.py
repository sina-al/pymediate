"""Wire the mediator (breaking the construction cycle) and run a short demo.

`build_mediator` is where the `Dispatcher` earns its keep: the orchestrator is constructed
with the dispatcher, the mediator is built from the provider, and only then is the mediator
bound into the dispatcher — the one ordering that resolves provider → orchestrator →
mediator → provider without a chicken-and-egg.
"""

import asyncio

from pymediate import Mediator, Services

from .dispatch import Dispatcher
from .domain import OrderStore, ShippingRates, Warehouse
from .operations import (
    PlaceOrder,
    PlaceOrderHandler,
    QuoteShippingHandler,
    ReserveStockHandler,
)


def build_mediator(
    *,
    warehouse: Warehouse | None = None,
    rates: ShippingRates | None = None,
    store: OrderStore | None = None,
) -> Mediator:
    """Wire a mediator whose `PlaceOrder` handler composes two sub-operations.

    Args:
        warehouse: Stock-reservation collaborator; a fresh one when omitted.
        rates: Shipping-rates collaborator; a fresh one when omitted.
        store: Order storage; a fresh empty store when omitted.

    Returns:
        A mediator wired with the two leaf handlers and the composing handler.
    """
    warehouse = warehouse if warehouse is not None else Warehouse()
    rates = rates if rates is not None else ShippingRates()
    store = store if store is not None else OrderStore()

    dispatch = Dispatcher()  # constructed empty; bound to the mediator below
    services = Services()
    services.add(ReserveStockHandler(warehouse))
    services.add(QuoteShippingHandler(rates))
    services.add(PlaceOrderHandler(dispatch, store))
    mediator = Mediator(services.provider())
    dispatch.bind(mediator)  # final step: now the orchestrator can send() sub-requests
    return mediator


async def main() -> None:
    """Place one order and show the two sub-operations overlapping."""
    # One shared trace both collaborators append to, so the printed order is their real
    # interleaving — not a reconstruction.
    trace: list[str] = []
    warehouse = Warehouse(trace=trace)
    rates = ShippingRates(trace=trace)
    mediator = build_mediator(warehouse=warehouse, rates=rates)

    order = await mediator.send(PlaceOrder(items=["pen", "notebook"]))
    print(
        f"Placed order {order.order_id}: reservation={order.reservation_id}, "
        f"shipping={order.shipping_cost}"
    )

    print("Sub-request timeline (both start before either finishes):")
    for entry in trace:
        print(f"  {entry}")


def run() -> None:
    """Console-script entry point (`uv run taskboard`)."""
    asyncio.run(main())


if __name__ == "__main__":
    run()
