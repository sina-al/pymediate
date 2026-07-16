"""The domain: two stores with different shapes, and the messages that cross between them.

CQRS in PyMediate isn't extra machinery — it's a naming convention over request types, plus
the discipline of giving the write side and the read side **separate stores that can evolve
independently**. That split is what this module makes visible:

- ``WriteStore`` is normalized — the shape a write needs to validate and mutate safely.
- ``ReadStore`` is denormalized — precomputed fields (``in_stock``, ``price_tier``) a reader
  wants, that the write side never stores. It's kept in sync by subscribing to the events the
  command handlers publish (see ``handlers.py``) — the same fan-out taught in 020-events.

Commands and queries both subclass ``Request``, dispatch through the same ``Mediator.send``,
and share nothing but that base class — CQRS is the discipline of writing two handlers instead
of one, not a different dispatch path.
"""

from dataclasses import dataclass, field
from typing import Any

from pymediate.sync import Event, Mediator, Request

# ---- Write-side record: normalized, exactly what a write needs ----


@dataclass
class Product:
    """The write-side record. No derived fields — those belong on the read side."""

    product_id: int
    name: str
    price: float
    stock: int


class WriteStore:
    """The write side: a normalized primary store, indexed by id."""

    def __init__(self) -> None:
        self._products: dict[int, Product] = {}
        self._next_id = 1

    def create(self, name: str, price: float, stock: int) -> Product:
        """Insert a new product and return the stored record."""
        product = Product(product_id=self._next_id, name=name, price=price, stock=stock)
        self._products[product.product_id] = product
        self._next_id += 1
        return product

    def adjust_stock(self, product_id: int, delta: int) -> Product:
        """Apply a stock delta to an existing product and return the updated record."""
        product = self._products[product_id]
        product.stock += delta
        return product


# ---- Read-side record: denormalized, precomputed for a reader ----


@dataclass
class ProductView:
    """The read-side record — richer than ``Product``, and never written to directly."""

    product_id: int
    name: str
    price: float
    stock: int
    in_stock: bool
    price_tier: str


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
    """No product exists with the given id, on the read side."""

    def __init__(self, product_id: int) -> None:
        self.product_id = product_id
        super().__init__(f"product not found: {product_id}")


class ReadStore:
    """The read side: a denormalized projection, written only by the event projectors.

    ``reads`` counts calls through ``find``/``search`` — the query path — so a test can
    show the read model changing without ever touching ``WriteStore``.
    """

    def __init__(self) -> None:
        self._views: dict[int, ProductView] = {}
        self.reads = 0

    def upsert(self, view: ProductView) -> None:
        """Replace the stored view for a product. Called only by the projectors."""
        self._views[view.product_id] = view

    def peek(self, product_id: int) -> ProductView | None:
        """Look up a view without counting it as a query read. For projector use only."""
        return self._views.get(product_id)

    def find(self, product_id: int) -> ProductView | None:
        """Look up a single product view — the query path."""
        self.reads += 1
        return self._views.get(product_id)

    def search(self, *, in_stock_only: bool = False) -> list[ProductView]:
        """List product views, optionally filtered to those in stock — the query path."""
        self.reads += 1
        views = list(self._views.values())
        if in_stock_only:
            views = [v for v in views if v.in_stock]
        return views


# ---- Events: how the read side learns what the write side did ----


@dataclass
class ProductCreated(Event):
    """Announces a new product; the read-side projector builds its first view from this."""

    product_id: int
    name: str
    price: float
    stock: int


@dataclass
class StockAdjusted(Event):
    """Announces a stock change, carrying the resulting stock so the projector needn't ask."""

    product_id: int
    delta: int
    new_stock: int


class LateBoundPublisher:
    """Lets a command handler publish, even though the ``Mediator`` doesn't exist yet.

    ``app.build_mediator`` constructs this first, hands it to the command handlers,
    builds the ``Mediator`` from that same ``Services`` collection, then calls ``bind`` —
    closing the loop so publishing reaches the read-model projectors.
    """

    def __init__(self) -> None:
        self._mediator: Mediator | None = None

    def bind(self, mediator: Mediator) -> None:
        """Attach the mediator that publishes will forward to."""
        self._mediator = mediator

    def publish(self, event: Event) -> None:
        """Forward an event to the bound mediator."""
        if self._mediator is None:
            raise RuntimeError("LateBoundPublisher.publish called before bind()")
        self._mediator.publish(event)


# ---- Commands: change state, return the minimum the caller needs ----


@dataclass
class ProductId:
    """A command response carrying only what the caller needs to proceed: the new id."""

    product_id: int


@dataclass
class StockAdjustedResult:
    """A command response: just enough to confirm the write, not the full read model."""

    product_id: int
    new_stock: int


@dataclass
class CreateProduct(Request[ProductId]):
    """Create a product. The command owns validation; the response is minimal."""

    name: str
    price: float
    stock: int = 0


@dataclass
class AdjustStock(Request[StockAdjustedResult]):
    """Change a product's stock by a delta, positive or negative."""

    product_id: int
    delta: int


# ---- Queries: read state, return the rich, fully-populated view ----


@dataclass
class BaseQuery(Request[Any]):
    """Marker base for every read-only request. Binds no dispatch machinery of its own —
    it exists so the read side is a family, symmetric with the write side's commands.
    """


@dataclass
class GetProduct(BaseQuery, Request[ProductView]):
    """Fetch one product's read-side view."""

    product_id: int


@dataclass
class SearchProducts(BaseQuery, Request[list[ProductView]]):
    """List product views, optionally restricted to those currently in stock."""

    in_stock_only: bool = field(default=False)
