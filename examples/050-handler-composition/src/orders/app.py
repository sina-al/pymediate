"""Wire the mediator and run a short demo.

The wiring is where the construction cycle gets closed. ``PlaceOrderHandler`` needs a
``Sender``, but the mediator doesn't exist until every handler is registered — so we
register a ``LateBoundSender``, build the mediator, and then ``bind`` it. Two extra lines,
and the composing handler can dispatch back into the very mediator it belongs to.
"""

import asyncio

from pymediate import Mediator, Services

from .domain import (
    LateBoundSender,
    PaymentGateway,
    PlaceOrder,
    Warehouse,
)
from .handlers import (
    ChargePaymentHandler,
    OrderConfirmation,
    PlaceOrderHandler,
    ReserveStockHandler,
    SalesAnalytics,
)


def build_mediator(
    *,
    warehouse: Warehouse | None = None,
    gateway: PaymentGateway | None = None,
    journal: list[str] | None = None,
) -> Mediator:
    """Wire the handlers, subscribers, and the late-bound sender into a mediator.

    Args:
        warehouse: Stock levels; a warehouse holding 10 ``WIDGET`` when omitted.
        gateway: Payment gateway; a fresh, accept-everything gateway when omitted.
        journal: Shared list the handlers append their markers to; a new list when omitted.

    Returns:
        A mediator that can route ``PlaceOrder`` and the sub-requests it dispatches.
    """
    warehouse = warehouse if warehouse is not None else Warehouse(stock={"WIDGET": 10})
    gateway = gateway if gateway is not None else PaymentGateway()
    journal = journal if journal is not None else []

    sender = LateBoundSender()

    services = Services()
    services.add(ReserveStockHandler(warehouse, journal))
    services.add(ChargePaymentHandler(gateway, journal))
    services.add(OrderConfirmation(journal))
    services.add(SalesAnalytics(journal))
    services.add(PlaceOrderHandler(sender, journal))  # depends on the sender, not the mediator

    mediator = Mediator(services.provider())
    sender.bind(mediator)  # subsequent sender calls now forward to this mediator
    return mediator


async def main() -> None:
    """Place one order and print the journal, showing the two sub-requests overlap."""
    journal: list[str] = []
    mediator = build_mediator(journal=journal)

    order = await mediator.send(PlaceOrder("cust-1", sku="WIDGET", quantity=2, amount_cents=1999))
    print(
        f"Placed order #{order.order_id} for {order.reservation.quantity} x "
        f"{order.reservation.sku}, charged {order.receipt.amount_cents}c"
    )

    print("Journal (top to bottom = order of execution):")
    for entry in journal:
        print(f"  {entry}")


def run() -> None:
    """Console-script entry point (``uv run orders``)."""
    asyncio.run(main())


if __name__ == "__main__":
    run()
