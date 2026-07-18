"""Command handlers write; query handlers read; one event handler notifies the worker.

Each command handler touches only ``WriteStore`` (domain row + outbox row, atomically) and
then publishes ``OutboxAppended``. Each query handler depends on ``ReadModel``, which does not
expose checkpoint updates or batch application. The benchmark-only
``NaiveInventoryReportHandler`` reads the write store to provide a comparison.
"""

from pymediate import EventHandler, RequestHandler

from .domain import (
    AdjustStock,
    AdjustStockResult,
    CreateProduct,
    CreateProductResult,
    GetInventoryReport,
    GetInventoryReportNaive,
    GetProduct,
    LateBoundPublisher,
    OutboxAppended,
    ProductNotFoundError,
    ProductView,
    SearchProducts,
    TierSummary,
)
from .projection import ProjectionWorker
from .read_store import ReadModel
from .write_store import WriteStore

# ---- Command handlers: write the outbox transaction, then publish a notification ----


class CreateProductHandler(RequestHandler[CreateProduct]):
    """Creates a product and its outbox event in one transaction, then announces it."""

    def __init__(self, store: WriteStore, publisher: LateBoundPublisher) -> None:
        self._store = store
        self._publisher = publisher

    async def __call__(self, request: CreateProduct) -> CreateProductResult:
        ack = self._store.create(request.name, request.price, request.stock)
        await self._publisher.publish(OutboxAppended(sequence=ack.outbox_position))
        return CreateProductResult(
            product_id=ack.product.product_id, outbox_position=ack.outbox_position
        )


class AdjustStockHandler(RequestHandler[AdjustStock]):
    """Adjusts stock and its outbox event in one transaction, then announces it."""

    def __init__(self, store: WriteStore, publisher: LateBoundPublisher) -> None:
        self._store = store
        self._publisher = publisher

    async def __call__(self, request: AdjustStock) -> AdjustStockResult:
        ack = self._store.adjust_stock(request.product_id, request.delta)
        await self._publisher.publish(OutboxAppended(sequence=ack.outbox_position))
        return AdjustStockResult(
            product_id=ack.product.product_id,
            new_stock=ack.product.stock,
            outbox_position=ack.outbox_position,
        )


# ---- Query handlers: read the read model, and only the read model ----


class GetProductHandler(RequestHandler[GetProduct]):
    """Fetches one product's read-side view — richer than anything the write side stores."""

    def __init__(self, store: ReadModel) -> None:
        self._store = store

    async def __call__(self, request: GetProduct) -> ProductView:
        view = self._store.find(request.product_id)
        if view is None:
            raise ProductNotFoundError(request.product_id)
        return view


class SearchProductsHandler(RequestHandler[SearchProducts]):
    """Lists product views, optionally filtered to those in stock."""

    def __init__(self, store: ReadModel) -> None:
        self._store = store

    async def __call__(self, request: SearchProducts) -> list[ProductView]:
        return self._store.search(in_stock_only=request.in_stock_only)


class InventoryReportHandler(RequestHandler[GetInventoryReport]):
    """Rolls the catalog up by tier off the DuckDB read model — the analytical read."""

    def __init__(self, store: ReadModel) -> None:
        self._store = store

    async def __call__(self, request: GetInventoryReport) -> list[TierSummary]:
        return self._store.inventory_report()


class NaiveInventoryReportHandler(RequestHandler[GetInventoryReportNaive]):
    """The benchmark baseline: the same rollup, run straight off the SQLite write store.

    Depends on ``WriteStore`` on purpose. Reaching into the OLTP store for analytics is the
    anti-pattern the read side exists to avoid — here only so the benchmark can time both.
    """

    def __init__(self, store: WriteStore) -> None:
        self._store = store

    async def __call__(self, request: GetInventoryReportNaive) -> list[TierSummary]:
        return self._store.inventory_report_naive()


# ---- The notification: an event handler that wakes the worker ----


class WakeProjector(EventHandler[OutboxAppended]):
    """Notify the projection worker that new outbox rows may be available.

    Writing to DuckDB here would put the read-model write inside the command's ``send`` call
    and recreate the failure boundary that the outbox removes. The worker performs the durable
    write outside the request.
    """

    def __init__(self, worker: ProjectionWorker) -> None:
        self._worker = worker

    async def __call__(self, event: OutboxAppended) -> None:
        self._worker.wake()
