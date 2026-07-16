"""Wire the write side, the read side, and the event that connects them, then run a demo.

Every handler above registers on **one** ``Services`` collection and dispatches through
**one** ``Mediator`` — commands and queries share the exact same machinery. CQRS lives
entirely in which store each handler touches, not in a second mediator or a parallel
dispatch path.
"""

import asyncio

from pymediate import Mediator, Services

from .domain import (
    AdjustStock,
    CreateProduct,
    GetProduct,
    LateBoundPublisher,
    ReadStore,
    SearchProducts,
    WriteStore,
)
from .handlers import (
    AdjustStockHandler,
    CreateProductHandler,
    GetProductHandler,
    ProductCreatedProjector,
    SearchProductsHandler,
    StockAdjustedProjector,
)


def build_mediator(
    write_store: WriteStore | None = None,
    read_store: ReadStore | None = None,
) -> Mediator:
    """Wire the command side, the query side, and the projectors onto one mediator.

    Args:
        write_store: The normalized primary store; a fresh empty store when omitted.
        read_store: The denormalized read store; a fresh empty store when omitted.

    Returns:
        A mediator that dispatches commands, queries, and the events between them.
    """
    write_store = write_store if write_store is not None else WriteStore()
    read_store = read_store if read_store is not None else ReadStore()
    publisher = LateBoundPublisher()

    services = Services()
    services.add(CreateProductHandler(write_store, publisher))
    services.add(AdjustStockHandler(write_store, publisher))
    services.add(GetProductHandler(read_store))
    services.add(SearchProductsHandler(read_store))
    services.add(ProductCreatedProjector(read_store))
    services.add(StockAdjustedProjector(read_store))

    mediator = Mediator(services.provider())
    publisher.bind(mediator)  # close the loop: command handlers can now publish through it
    return mediator


async def main() -> None:
    """Create a product, adjust its stock, then read it back through the denormalized view."""
    mediator = build_mediator()

    created = await mediator.send(CreateProduct(name="Keyboard", price=49.99, stock=10))
    print(f"CreateProduct -> {created}")

    adjusted = await mediator.send(AdjustStock(product_id=created.product_id, delta=-3))
    print(f"AdjustStock   -> {adjusted}")

    view = await mediator.send(GetProduct(product_id=created.product_id))
    print(f"GetProduct    -> {view}")

    results = await mediator.send(SearchProducts(in_stock_only=True))
    print(f"SearchProducts -> {len(results)} product(s) in stock")


def run() -> None:
    """Console-script entry point (``uv run catalog``)."""
    asyncio.run(main())


if __name__ == "__main__":
    run()
