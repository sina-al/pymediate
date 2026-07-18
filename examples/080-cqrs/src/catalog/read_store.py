"""The read side: a denormalized DuckDB table with a projection checkpoint (OLAP).

DuckDB is a column store — it keeps each column together, so a query that scans one or two
columns across every row (``inventory_report`` below) reads only those columns and aggregates
them in bulk. That's the shape of an analytical read, and it's why the read side is DuckDB and
not the SQLite write store. ``benchmark.py`` measures the difference.

Two ``Protocol``s fence the store's two surfaces so the rest of the app can only touch the
half it should:

- **``ReadModel``** — ``find`` / ``search`` / ``inventory_report``. Query handlers depend on
  this, so a query handler literally cannot advance the checkpoint or apply a batch.
- **``ProjectionTarget``** — ``checkpoint`` / ``apply_batch``. The projector depends on this,
  so it never reaches into the query surface.

``ReadStore`` implements both — it's one DuckDB file underneath — but nothing outside this
module ever holds a reference typed as ``ReadStore``. The type checker enforces the split; it
isn't a comment asking nicely.
"""

from pathlib import Path
from typing import Protocol

import duckdb

from .domain import (
    PRODUCT_CREATED,
    STOCK_ADJUSTED,
    OutboxEvent,
    Product,
    ProductView,
    TierSummary,
    project,
)

_PROJECTION = "product_view"
_VIEW_COLUMNS = "product_id, name, price, stock, in_stock, price_tier"

_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS product_view ("
    "  product_id INTEGER PRIMARY KEY,"
    "  name       VARCHAR,"
    "  price      DOUBLE,"
    "  stock      INTEGER,"
    "  in_stock   BOOLEAN,"
    "  price_tier VARCHAR)",
    "CREATE TABLE IF NOT EXISTS projection_checkpoint ("
    "  projection_name VARCHAR PRIMARY KEY,"
    "  last_sequence   BIGINT NOT NULL)",
    "INSERT INTO projection_checkpoint VALUES ('product_view', 0) ON CONFLICT DO NOTHING",
)


class ReadModel(Protocol):
    """The read side as a query handler is allowed to see it: lookups and aggregates only."""

    def find(self, product_id: int) -> ProductView | None: ...
    def search(self, *, in_stock_only: bool = False) -> list[ProductView]: ...
    def inventory_report(self) -> list[TierSummary]: ...


class ProjectionTarget(Protocol):
    """The read side as the projector is allowed to see it: read the checkpoint, apply a
    batch. Nothing from ``ReadModel``'s query surface.
    """

    def checkpoint(self) -> int: ...
    def apply_batch(self, events: list[OutboxEvent]) -> None: ...


class ReadStore:
    """The read side: a denormalized DuckDB table plus the projector's checkpoint.

    The single DuckDB connection is the sole writer. This example runs the projector as one
    asyncio task on the same thread as everything else, so one connection is enough; a
    genuinely multi-threaded projector would use ``conn.cursor()`` per thread (DuckDB's
    documented in-process concurrency pattern). See ``docs/architecture.md``.
    """

    def __init__(self, database: Path | str) -> None:
        self._conn = duckdb.connect(str(database))
        for statement in _SCHEMA:
            self._conn.execute(statement)

    # -- ProjectionTarget: written only by the projector --

    def checkpoint(self) -> int:
        """The sequence of the last outbox event applied to the read model."""
        row = self._conn.execute(
            "SELECT last_sequence FROM projection_checkpoint WHERE projection_name = ?",
            [_PROJECTION],
        ).fetchone()
        assert row is not None  # seeded to 0 at construction
        return int(row[0])

    def apply_batch(self, events: list[OutboxEvent]) -> None:
        """Apply an ordered batch and advance the checkpoint — in one DuckDB transaction.

        The projection changes and the checkpoint advance commit together, so a crash can
        never leave the read model ahead of or behind its recorded position. A failed apply
        rolls both back and the batch is retried from the same checkpoint.
        """
        if not events:
            return
        conn = self._conn
        conn.execute("BEGIN TRANSACTION")
        try:
            for event in events:
                self._apply(event)
            conn.execute(
                "UPDATE projection_checkpoint SET last_sequence = ? WHERE projection_name = ?",
                [events[-1].sequence, _PROJECTION],
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

    def _apply(self, event: OutboxEvent) -> None:
        if event.event_type == PRODUCT_CREATED:
            view = project(Product(**event.payload))
            self._conn.execute(
                f"INSERT INTO product_view ({_VIEW_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT (product_id) DO UPDATE SET "
                "name = excluded.name, price = excluded.price, stock = excluded.stock, "
                "in_stock = excluded.in_stock, price_tier = excluded.price_tier",
                [
                    view.product_id,
                    view.name,
                    view.price,
                    view.stock,
                    view.in_stock,
                    view.price_tier,
                ],
            )
        elif event.event_type == STOCK_ADJUSTED:
            new_stock = event.payload["new_stock"]
            self._conn.execute(
                "UPDATE product_view SET stock = ?, in_stock = ? WHERE product_id = ?",
                [new_stock, new_stock > 0, event.payload["product_id"]],
            )
        else:  # pragma: no cover - guards against an event type the projector doesn't know
            raise ValueError(f"unknown outbox event type: {event.event_type}")

    # -- ReadModel: read by query handlers --

    def find(self, product_id: int) -> ProductView | None:
        """Look up a single product view."""
        row = self._conn.execute(
            f"SELECT {_VIEW_COLUMNS} FROM product_view WHERE product_id = ?",
            [product_id],
        ).fetchone()
        return ProductView(*row) if row is not None else None

    def search(self, *, in_stock_only: bool = False) -> list[ProductView]:
        """List product views, optionally filtered to those in stock."""
        sql = f"SELECT {_VIEW_COLUMNS} FROM product_view"
        if in_stock_only:
            sql += " WHERE in_stock"
        sql += " ORDER BY product_id"
        return [ProductView(*row) for row in self._conn.execute(sql).fetchall()]

    def inventory_report(self) -> list[TierSummary]:
        """Roll the whole catalog up by price tier — the analytical query, the OLAP payoff.

        A scan-and-aggregate over the ``price_tier`` and ``price``/``stock`` columns. On
        DuckDB's columnar storage it reads only those columns; on a row store the same query
        walks every row in full.
        """
        rows = self._conn.execute(
            "SELECT price_tier, count(*), sum(price * stock), avg(price) "
            "FROM product_view GROUP BY price_tier ORDER BY price_tier"
        ).fetchall()
        return [
            TierSummary(tier, count, round(value, 2), round(avg, 2))
            for tier, count, value, avg in rows
        ]

    def close(self) -> None:
        """Close the underlying connection."""
        self._conn.close()
