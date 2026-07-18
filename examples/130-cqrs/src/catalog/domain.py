"""Messages and value types for the catalog example.

Command Query Responsibility Segregation (CQRS) separates operations that change state from
operations that read state. PyMediate uses the same ``Request`` and ``Mediator.send`` API for
both. The separation comes from the handlers and models used on each side. This module holds
only the domain vocabulary:

- the **commands** (``CreateProduct``, ``AdjustStock``) and their minimal responses;
- the **queries** (``GetProduct``, ``SearchProducts``, ``GetInventoryReport``, and the
  benchmark-only ``GetInventoryReportNaive``) and the rich views they return;
- the **value types** (``Product`` for the write side, ``ProductView`` for the read side,
  ``TierSummary`` for the analytical rollup) and the ``project`` function between them;
- the **outbox vocabulary** — ``OutboxEvent`` (a row read back off the SQLite outbox) and the
  two event-type constants — plus ``OutboxAppended``, the one PyMediate ``Event`` this example
  publishes, used only to notify the projection worker.

The stores, worker, and handlers are defined in separate modules. Start with the README's file
table.
"""

from dataclasses import dataclass
from typing import Any

from pymediate import Event, Mediator, Request

# ---- Value types: the write-side record, the read-side view, the rollup ----


@dataclass
class Product:
    """The write-side record. No derived fields — those belong on the read side."""

    product_id: int
    name: str
    price: float
    stock: int


@dataclass
class ProductView:
    """The read-side record — richer than ``Product``, and never written to directly."""

    product_id: int
    name: str
    price: float
    stock: int
    in_stock: bool
    price_tier: str


@dataclass
class TierSummary:
    """One row of the tier rollup: the analytical query's result, per price tier."""

    price_tier: str
    product_count: int
    inventory_value: float  # sum(price * stock) across the tier
    avg_price: float


def _price_tier(price: float) -> str:
    """Bucket a price into a tier — a derived field only the read side needs."""
    if price < 20:
        return "budget"
    if price < 100:
        return "standard"
    return "premium"


def project(product: Product) -> ProductView:
    """Compute a read-side view from a write-side record. The projection, made concrete."""
    return ProductView(
        product_id=product.product_id,
        name=product.name,
        price=product.price,
        stock=product.stock,
        in_stock=product.stock > 0,
        price_tier=_price_tier(product.price),
    )


class ProductNotFoundError(Exception):
    """No product exists with the given id."""

    def __init__(self, product_id: int) -> None:
        self.product_id = product_id
        super().__init__(f"product not found: {product_id}")


# ---- Outbox vocabulary: durable events, and the wake-up notification ----

PRODUCT_CREATED = "ProductCreated"
STOCK_ADJUSTED = "StockAdjusted"


@dataclass
class OutboxEvent:
    """One row read back off the SQLite outbox, ready for the projector to apply.

    The payload carries **absolute resulting state** (``StockAdjusted`` reports the new stock
    level, not a delta), so re-applying a batch after a crash is idempotent — see the
    architecture notes in ``docs/architecture.md``.
    """

    sequence: int
    event_type: str
    payload: dict[str, Any]


@dataclass
class OutboxAppended(Event):
    """Published after a command commits, to notify the projection worker.

    This is a *latency optimisation only* — the durable record is the outbox row, and the
    worker also polls. Drop this event entirely and the read side still catches up on the next
    poll. It carries the new sequence purely so a subscriber could log how far behind it is.
    """

    sequence: int


class LateBoundPublisher:
    """Lets a command handler publish, even though the ``Mediator`` doesn't exist yet.

    ``app.build_app`` constructs this first, hands it to the command handlers, builds the
    ``Mediator`` from that same ``Services`` collection, then calls ``bind`` — closing the loop
    so publishing reaches the wake-up handler. The same pattern 050-handler-composition uses.
    """

    def __init__(self) -> None:
        self._mediator: Mediator | None = None

    def bind(self, mediator: Mediator) -> None:
        """Attach the mediator that publishes will forward to."""
        self._mediator = mediator

    async def publish(self, event: Event) -> None:
        """Forward an event to the bound mediator."""
        if self._mediator is None:
            raise RuntimeError("LateBoundPublisher.publish called before bind()")
        await self._mediator.publish(event)


# ---- Commands: change state, return the minimum the caller needs ----


@dataclass
class CreateProductResult:
    """A command response: the new id, plus the outbox position for read-your-writes."""

    product_id: int
    outbox_position: int


@dataclass
class AdjustStockResult:
    """A command response: enough to confirm the write, plus the outbox position."""

    product_id: int
    new_stock: int
    outbox_position: int


@dataclass
class CreateProduct(Request[CreateProductResult]):
    """Create a product and return its id and outbox position."""

    name: str
    price: float
    stock: int = 0


@dataclass
class AdjustStock(Request[AdjustStockResult]):
    """Change a product's stock by a delta, positive or negative."""

    product_id: int
    delta: int


# ---- Queries: read state, return the rich, fully-populated view ----


@dataclass
class GetProduct(Request[ProductView]):
    """Fetch one product's read-side view."""

    product_id: int


@dataclass
class SearchProducts(Request[list[ProductView]]):
    """List product views, optionally restricted to those currently in stock."""

    in_stock_only: bool = False


@dataclass
class GetInventoryReport(Request[list[TierSummary]]):
    """Roll the catalog up by price tier — the analytical query, answered by the DuckDB read
    model.
    """


@dataclass
class GetInventoryReportNaive(Request[list[TierSummary]]):
    """The same rollup, answered the naive way — straight off the SQLite write model.

    It exists only so ``benchmark.py`` can time the identical question against both engines
    through the mediator. You would not ship this: running analytics on your OLTP store is the
    very thing a read model exists to avoid.
    """
