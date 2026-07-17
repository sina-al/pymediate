"""Two stores on two engines, and the messages that cross between them.

CQRS in PyMediate isn't extra machinery — it's a naming convention over request types, plus
the discipline of giving the write side and the read side **separate stores that can evolve
independently**. This example makes that split physical: the two stores run on two different
database engines, each picked for what its side actually does.

- ``WriteStore`` is a normalized **SQLite** table — row-oriented storage built for
  transactional writes (insert a product, get its generated id back, adjust one row's stock).
  This is the OLTP side.
- ``ReadStore`` is a denormalized **DuckDB** table — columnar storage built for analytical
  reads that scan and aggregate many rows. It carries precomputed fields (``in_stock``,
  ``price_tier``) the write side never stores, and it answers the tier-rollup query
  (``inventory_report``) that a row store would have to grind through row by row. This is the
  OLAP side. It's kept in sync only by subscribing to the events the command handlers publish
  (see ``handlers.py``) — the same fan-out taught in 020-events.

Commands and queries both subclass ``Request``, dispatch through the same ``Mediator.send``,
and share nothing but that base class. The handlers don't know or care that one store is
SQLite and the other DuckDB — swapping the dicts of the in-memory version for real engines
changed only these store classes, not a line of handler or wiring code.
"""

import sqlite3
from dataclasses import dataclass, field
from typing import Any

import duckdb
from pymediate.sync import Event, Mediator, Request

# ---- Write-side store: a normalized SQLite table (OLTP) ----


@dataclass
class Product:
    """The write-side record. No derived fields — those belong on the read side."""

    product_id: int
    name: str
    price: float
    stock: int


_WRITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    product_id INTEGER PRIMARY KEY,
    name       TEXT    NOT NULL,
    price      REAL    NOT NULL,
    stock      INTEGER NOT NULL
)
"""


class WriteStore:
    """The write side: a normalized SQLite table, indexed by id.

    SQLite is a row store — it keeps each product's fields together, which is exactly what a
    write touches: insert one row, or update one row's stock. The ``product_id`` is generated
    by the database on insert, the way a primary key usually is.
    """

    def __init__(self, connection: sqlite3.Connection | None = None) -> None:
        self._conn = connection if connection is not None else sqlite3.connect(":memory:")
        self._conn.execute(_WRITE_SCHEMA)

    def create(self, name: str, price: float, stock: int) -> Product:
        """Insert a new product and return the stored record, id and all."""
        cursor = self._conn.execute(
            "INSERT INTO products (name, price, stock) VALUES (?, ?, ?)",
            (name, price, stock),
        )
        self._conn.commit()
        product_id = cursor.lastrowid
        assert product_id is not None  # a successful INSERT always yields a rowid
        return Product(product_id=product_id, name=name, price=price, stock=stock)

    def adjust_stock(self, product_id: int, delta: int) -> Product:
        """Apply a stock delta to an existing product and return the updated record."""
        self._conn.execute(
            "UPDATE products SET stock = stock + ? WHERE product_id = ?",
            (delta, product_id),
        )
        self._conn.commit()
        row = self._conn.execute(
            "SELECT product_id, name, price, stock FROM products WHERE product_id = ?",
            (product_id,),
        ).fetchone()
        assert row is not None  # the caller only adjusts stock for a product that exists
        return Product(product_id=row[0], name=row[1], price=row[2], stock=row[3])


# ---- Read-side records: denormalized, precomputed for a reader ----


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
    """No product exists with the given id, on the read side."""

    def __init__(self, product_id: int) -> None:
        self.product_id = product_id
        super().__init__(f"product not found: {product_id}")


# ---- Read-side store: a denormalized DuckDB table (OLAP) ----

_VIEW_COLUMNS = "product_id, name, price, stock, in_stock, price_tier"

_READ_SCHEMA = """
CREATE TABLE products (
    product_id INTEGER PRIMARY KEY,
    name       VARCHAR,
    price      DOUBLE,
    stock      INTEGER,
    in_stock   BOOLEAN,
    price_tier VARCHAR
)
"""


class ReadStore:
    """The read side: a denormalized DuckDB table, written only by the event projectors.

    DuckDB is a column store — it keeps each column together, so a query that scans one or
    two columns across every row (``inventory_report`` below) reads only those columns and
    aggregates them in bulk. That's the shape of an analytical read, and it's why the read
    side is DuckDB and not the SQLite write store. ``benchmark.py`` measures the difference.

    ``reads`` counts calls through the query path (``find``/``search``/``inventory_report``)
    so a test can show the read model changing without ever touching ``WriteStore``.
    """

    def __init__(self, connection: duckdb.DuckDBPyConnection | None = None) -> None:
        self._conn = connection if connection is not None else duckdb.connect()
        self._conn.execute(_READ_SCHEMA)
        self.reads = 0

    def upsert(self, view: ProductView) -> None:
        """Insert or replace the stored view for a product. Called only by the projectors."""
        self._conn.execute(
            f"INSERT INTO products ({_VIEW_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT (product_id) DO UPDATE SET "
            "name = excluded.name, price = excluded.price, stock = excluded.stock, "
            "in_stock = excluded.in_stock, price_tier = excluded.price_tier",
            (view.product_id, view.name, view.price, view.stock, view.in_stock, view.price_tier),
        )

    def peek(self, product_id: int) -> ProductView | None:
        """Look up a view without counting it as a query read. For projector use only."""
        row = self._conn.execute(
            f"SELECT {_VIEW_COLUMNS} FROM products WHERE product_id = ?",
            (product_id,),
        ).fetchone()
        return ProductView(*row) if row is not None else None

    def find(self, product_id: int) -> ProductView | None:
        """Look up a single product view — the query path."""
        self.reads += 1
        return self.peek(product_id)

    def search(self, *, in_stock_only: bool = False) -> list[ProductView]:
        """List product views, optionally filtered to those in stock — the query path."""
        self.reads += 1
        sql = f"SELECT {_VIEW_COLUMNS} FROM products"
        if in_stock_only:
            sql += " WHERE in_stock"
        sql += " ORDER BY product_id"
        return [ProductView(*row) for row in self._conn.execute(sql).fetchall()]

    def inventory_report(self) -> list[TierSummary]:
        """Roll the whole catalog up by price tier — the analytical query, the OLAP payoff.

        A scan-and-aggregate over every product. On DuckDB's columnar storage it reads only
        the columns it needs; on a row store the same query walks every row in full. See
        ``benchmark.py`` for the gap at scale.
        """
        self.reads += 1
        rows = self._conn.execute(
            "SELECT price_tier, count(*), sum(price * stock), avg(price) "
            "FROM products GROUP BY price_tier ORDER BY price_tier"
        ).fetchall()
        return [
            TierSummary(
                price_tier=tier,
                product_count=count,
                inventory_value=round(value, 2),
                avg_price=round(avg, 2),
            )
            for tier, count, value, avg in rows
        ]


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


@dataclass
class GetInventoryReport(BaseQuery, Request[list[TierSummary]]):
    """Roll the catalog up by price tier — the analytical query DuckDB is built for."""
