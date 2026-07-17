"""Command handlers write; query handlers read; projectors keep the read side in sync.

Each command handler touches only ``WriteStore`` and publishes an event describing what
changed. Each query handler touches only ``ReadStore`` — it never reaches into the write
side, even though it could. That separation is the entire point: swap ``ReadStore`` for a
denormalized replica or a search index and no query handler's *caller* notices.
"""

from dataclasses import replace

from pymediate import EventHandler, RequestHandler

from .domain import (
    AdjustStock,
    CreateProduct,
    GetInventoryReport,
    GetProduct,
    LateBoundPublisher,
    Product,
    ProductCreated,
    ProductId,
    ProductNotFoundError,
    ProductView,
    ReadStore,
    SearchProducts,
    StockAdjusted,
    StockAdjustedResult,
    TierSummary,
    WriteStore,
    project,
)

# ---- Command handlers: write, then announce ----


class CreateProductHandler(RequestHandler[CreateProduct]):
    """Creates a product on the write side and announces it. Response: just the new id."""

    def __init__(self, store: WriteStore, publisher: LateBoundPublisher) -> None:
        self._store = store
        self._publisher = publisher

    async def __call__(self, request: CreateProduct) -> ProductId:
        product = self._store.create(request.name, request.price, request.stock)
        await self._publisher.publish(
            ProductCreated(
                product_id=product.product_id,
                name=product.name,
                price=product.price,
                stock=product.stock,
            )
        )
        return ProductId(product_id=product.product_id)


class AdjustStockHandler(RequestHandler[AdjustStock]):
    """Adjusts a product's stock and announces the result. Response: id and new stock."""

    def __init__(self, store: WriteStore, publisher: LateBoundPublisher) -> None:
        self._store = store
        self._publisher = publisher

    async def __call__(self, request: AdjustStock) -> StockAdjustedResult:
        product = self._store.adjust_stock(request.product_id, request.delta)
        await self._publisher.publish(
            StockAdjusted(
                product_id=product.product_id,
                delta=request.delta,
                new_stock=product.stock,
            )
        )
        return StockAdjustedResult(product_id=product.product_id, new_stock=product.stock)


# ---- Query handlers: read, and only read ----


class GetProductHandler(RequestHandler[GetProduct]):
    """Fetches one product's read-side view — richer than anything the write side stores."""

    def __init__(self, store: ReadStore) -> None:
        self._store = store

    async def __call__(self, request: GetProduct) -> ProductView:
        view = self._store.find(request.product_id)
        if view is None:
            raise ProductNotFoundError(request.product_id)
        return view


class SearchProductsHandler(RequestHandler[SearchProducts]):
    """Lists product views, optionally filtered to those in stock."""

    def __init__(self, store: ReadStore) -> None:
        self._store = store

    async def __call__(self, request: SearchProducts) -> list[ProductView]:
        return self._store.search(in_stock_only=request.in_stock_only)


class InventoryReportHandler(RequestHandler[GetInventoryReport]):
    """Rolls the whole catalog up by price tier — the analytical read DuckDB is built for."""

    def __init__(self, store: ReadStore) -> None:
        self._store = store

    async def __call__(self, request: GetInventoryReport) -> list[TierSummary]:
        return self._store.inventory_report()


# ---- Projectors: the read side's only writers, driven entirely by events ----


class ProductCreatedProjector(EventHandler[ProductCreated]):
    """Builds the first read-side view the moment a product is created."""

    def __init__(self, read_store: ReadStore) -> None:
        self._read_store = read_store

    async def __call__(self, event: ProductCreated) -> None:
        view = project(
            Product(
                product_id=event.product_id,
                name=event.name,
                price=event.price,
                stock=event.stock,
            )
        )
        self._read_store.upsert(view)


class StockAdjustedProjector(EventHandler[StockAdjusted]):
    """Updates the read-side view's stock (and derived ``in_stock``) after a stock change."""

    def __init__(self, read_store: ReadStore) -> None:
        self._read_store = read_store

    async def __call__(self, event: StockAdjusted) -> None:
        existing = self._read_store.peek(event.product_id)
        assert existing is not None  # ProductCreatedProjector always runs first
        updated = replace(existing, stock=event.new_stock, in_stock=event.new_stock > 0)
        self._read_store.upsert(updated)
