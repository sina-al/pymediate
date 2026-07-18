"""Wire the write side, the read side, and the projection worker; then run a demo.

Every handler registers on one ``Services`` collection and dispatches through one
``Mediator``. Commands and queries share the same dispatch machinery. Their handlers use
separate stores, and the outbox worker projects writes into the read model.
"""

import asyncio
import tempfile
from dataclasses import dataclass
from pathlib import Path

from pymediate import Mediator, Services

from .domain import (
    AdjustStock,
    CreateProduct,
    GetInventoryReport,
    GetProduct,
    LateBoundPublisher,
    SearchProducts,
)
from .handlers import (
    AdjustStockHandler,
    CreateProductHandler,
    GetProductHandler,
    InventoryReportHandler,
    NaiveInventoryReportHandler,
    SearchProductsHandler,
    WakeProjector,
)
from .projection import ProjectionWorker, Projector, wait_until_caught_up
from .read_store import ReadStore
from .write_store import WriteStore


@dataclass
class App:
    """Everything a caller needs: the mediator to dispatch through, and the moving parts."""

    mediator: Mediator
    worker: ProjectionWorker
    write_store: WriteStore
    read_store: ReadStore
    projector: Projector

    def close(self) -> None:
        """Close every open database connection."""
        self.projector.close()
        self.write_store.close()
        self.read_store.close()


def build_app(database_dir: Path | str) -> App:
    """Wire commands, queries, and the projection worker over a SQLite + DuckDB pair.

    Args:
        database_dir: Directory to hold ``write.sqlite`` and ``read.duckdb``.

    Returns:
        An ``App`` whose ``mediator`` dispatches commands and queries, and whose ``worker``
        projects the outbox into the read model once started.
    """
    directory = Path(database_dir)
    write_store = WriteStore(directory / "write.sqlite")
    read_store = ReadStore(directory / "read.duckdb")
    projector = Projector(directory / "write.sqlite", read_store)
    worker = ProjectionWorker(projector)
    publisher = LateBoundPublisher()

    services = Services()
    services.add(CreateProductHandler(write_store, publisher))
    services.add(AdjustStockHandler(write_store, publisher))
    services.add(GetProductHandler(read_store))
    services.add(SearchProductsHandler(read_store))
    services.add(InventoryReportHandler(read_store))
    services.add(NaiveInventoryReportHandler(write_store))
    services.add(WakeProjector(worker))

    mediator = Mediator(services.provider())
    publisher.bind(mediator)  # command handlers can now publish through this mediator
    return App(mediator, worker, write_store, read_store, projector)


async def main() -> None:
    """Write a catalog through commands, wait for the read model, then query it."""
    with tempfile.TemporaryDirectory() as tmp:
        app = build_app(tmp)
        worker_task = asyncio.create_task(app.worker.run())
        try:
            created = await app.mediator.send(CreateProduct(name="Keyboard", price=49.99, stock=10))
            print(f"CreateProduct      -> {created}")

            adjusted = await app.mediator.send(AdjustStock(product_id=created.product_id, delta=-3))
            print(f"AdjustStock        -> {adjusted}")

            await app.mediator.send(CreateProduct(name="USB-C Cable", price=8.5, stock=200))
            last = await app.mediator.send(CreateProduct(name="4K Monitor", price=329.0, stock=4))

            # The read side is eventually consistent: the commands above have committed to
            # SQLite, but the worker may not have projected them into DuckDB yet. Wait for the
            # checkpoint to reach the last write's outbox position before reading.
            print(
                f"read model at checkpoint {app.read_store.checkpoint()}, "
                f"waiting for outbox position {last.outbox_position}..."
            )
            await wait_until_caught_up(app.read_store, last.outbox_position)
            print(f"caught up at checkpoint {app.read_store.checkpoint()}")

            view = await app.mediator.send(GetProduct(product_id=created.product_id))
            print(f"GetProduct         -> {view}")

            results = await app.mediator.send(SearchProducts(in_stock_only=True))
            print(f"SearchProducts     -> {len(results)} product(s) in stock")

            report = await app.mediator.send(GetInventoryReport())
            print("GetInventoryReport ->")
            for tier in report:
                print(
                    f"    {tier.price_tier:<8} count={tier.product_count} "
                    f"value={tier.inventory_value} avg={tier.avg_price}"
                )
        finally:
            await app.worker.stop()
            await worker_task
            app.close()


def run() -> None:
    """Console-script entry point (``uv run catalog``)."""
    asyncio.run(main())


if __name__ == "__main__":
    run()
