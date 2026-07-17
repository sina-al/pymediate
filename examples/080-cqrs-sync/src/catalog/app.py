"""Wire the write side, the read side, and the event that connects them, then run a demo.

Every handler above registers on **one** ``Services`` collection and dispatches through
**one** ``Mediator`` — commands and queries share the exact same machinery. CQRS lives
entirely in which store each handler touches, not in a second mediator or a parallel
dispatch path.
"""

from pymediate.sync import Mediator, Services

from .domain import (
    AdjustStock,
    CreateProduct,
    GetInventoryReport,
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
    InventoryReportHandler,
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
    services.add(InventoryReportHandler(read_store))
    services.add(ProductCreatedProjector(read_store))
    services.add(StockAdjustedProjector(read_store))

    mediator = Mediator(services.provider())
    publisher.bind(mediator)  # close the loop: command handlers can now publish through it
    return mediator


def main() -> None:
    """Write a small catalog through commands, then read it back through the DuckDB views."""
    mediator = build_mediator()

    created = mediator.send(CreateProduct(name="Keyboard", price=49.99, stock=10))
    print(f"CreateProduct      -> {created}")

    adjusted = mediator.send(AdjustStock(product_id=created.product_id, delta=-3))
    print(f"AdjustStock        -> {adjusted}")

    mediator.send(CreateProduct(name="USB-C Cable", price=8.5, stock=200))
    mediator.send(CreateProduct(name="4K Monitor", price=329.0, stock=4))

    view = mediator.send(GetProduct(product_id=created.product_id))
    print(f"GetProduct         -> {view}")

    results = mediator.send(SearchProducts(in_stock_only=True))
    print(f"SearchProducts     -> {len(results)} product(s) in stock")

    report = mediator.send(GetInventoryReport())
    print("GetInventoryReport ->")
    for tier in report:
        print(
            f"    {tier.price_tier:<8} count={tier.product_count} "
            f"value={tier.inventory_value} avg={tier.avg_price}"
        )


def run() -> None:
    """Console-script entry point (``uv run catalog``)."""
    main()


if __name__ == "__main__":
    run()
