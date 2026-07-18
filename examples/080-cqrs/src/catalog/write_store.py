"""The write side: a normalized SQLite table plus a transactional outbox (OLTP).

SQLite is a row store — it keeps each product's fields together, which is exactly what a write
touches: insert one row, or update one row's stock. The interesting part is the **outbox**: a
command writes the domain row *and* an event row describing what changed **in one SQLite
transaction**. Either both land or neither does. There is no second database in this write
path, so there is no dual-write failure mode — the read model is built later, from the outbox,
by the projection worker (see ``projection.py``).

This is the canonical transactional-outbox pattern; ``docs/architecture.md`` explains why it
beats writing SQLite and DuckDB in the same command.
"""

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from .domain import PRODUCT_CREATED, STOCK_ADJUSTED, OutboxEvent, Product, TierSummary

_SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    product_id INTEGER PRIMARY KEY,
    name       TEXT    NOT NULL,
    price      REAL    NOT NULL,
    stock      INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS outbox (
    sequence     INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id     TEXT    NOT NULL UNIQUE,
    event_type   TEXT    NOT NULL,
    payload_json TEXT    NOT NULL,
    occurred_at  TEXT    NOT NULL
);
"""

# The naive rollup: computed straight off the write model, deriving the tier in the query
# (the write side never stores it). Same answer as the read model's GROUP BY, far more work at
# scale — that gap is what benchmark.py measures.
_NAIVE_REPORT_SQL = """
SELECT
    CASE
        WHEN price < 20  THEN 'budget'
        WHEN price < 100 THEN 'standard'
        ELSE 'premium'
    END AS price_tier,
    count(*), sum(price * stock), avg(price)
FROM products
GROUP BY price_tier
ORDER BY price_tier
"""


@dataclass(frozen=True)
class WriteAck:
    """What a command handler gets back: the stored record and its outbox position."""

    product: Product
    outbox_position: int


def _append_outbox(conn: sqlite3.Connection, event_type: str, payload: dict[str, object]) -> int:
    """Insert one outbox row and return its monotonically increasing sequence."""
    cursor = conn.execute(
        "INSERT INTO outbox (event_id, event_type, payload_json, occurred_at) VALUES (?, ?, ?, ?)",
        (str(uuid4()), event_type, json.dumps(payload), datetime.now(UTC).isoformat()),
    )
    sequence = cursor.lastrowid
    assert sequence is not None  # a successful INSERT always yields a rowid
    return int(sequence)


def read_outbox(conn: sqlite3.Connection, after_sequence: int, limit: int) -> list[OutboxEvent]:
    """Read the next ordered batch of outbox rows past ``after_sequence``.

    The projector calls this through its **own** connection — the outbox is a durable log it
    polls, not something it shares with the write path.
    """
    rows = conn.execute(
        "SELECT sequence, event_type, payload_json FROM outbox "
        "WHERE sequence > ? ORDER BY sequence LIMIT ?",
        (after_sequence, limit),
    ).fetchall()
    return [OutboxEvent(seq, event_type, json.loads(payload)) for seq, event_type, payload in rows]


class WriteStore:
    """The write side: a normalized SQLite table indexed by id, with a transactional outbox.

    Opened in autocommit mode (``isolation_level=None``) so the store controls its own
    ``BEGIN IMMEDIATE`` / ``COMMIT`` boundaries, and in WAL mode so the projector's separate
    read connection can poll the outbox without blocking writes.
    """

    def __init__(self, database: Path | str) -> None:
        self._conn = sqlite3.connect(database, isolation_level=None)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.executescript(_SCHEMA)

    def create(self, name: str, price: float, stock: int) -> WriteAck:
        """Insert a product and its ``ProductCreated`` outbox row in one transaction."""
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            cursor = conn.execute(
                "INSERT INTO products (name, price, stock) VALUES (?, ?, ?)",
                (name, price, stock),
            )
            product_id = cursor.lastrowid
            assert product_id is not None
            sequence = _append_outbox(
                conn,
                PRODUCT_CREATED,
                {"product_id": product_id, "name": name, "price": price, "stock": stock},
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        return WriteAck(Product(product_id, name, price, stock), sequence)

    def adjust_stock(self, product_id: int, delta: int) -> WriteAck:
        """Apply a stock delta and append a ``StockAdjusted`` outbox row in one transaction.

        The outbox payload carries the **resulting** stock level (absolute, not the delta), so
        the projector can apply it idempotently.
        """
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute(
                "UPDATE products SET stock = stock + ? WHERE product_id = ?",
                (delta, product_id),
            )
            row = conn.execute(
                "SELECT product_id, name, price, stock FROM products WHERE product_id = ?",
                (product_id,),
            ).fetchone()
            assert row is not None  # the caller only adjusts stock for a product that exists
            product = Product(row[0], row[1], row[2], row[3])
            sequence = _append_outbox(
                conn,
                STOCK_ADJUSTED,
                {"product_id": product.product_id, "new_stock": product.stock},
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        return WriteAck(product, sequence)

    def inventory_report_naive(self) -> list[TierSummary]:
        """Roll the catalog up by tier straight off the row store — the naive baseline."""
        rows = self._conn.execute(_NAIVE_REPORT_SQL).fetchall()
        return [
            TierSummary(tier, count, round(value, 2), round(avg, 2))
            for tier, count, value, avg in rows
        ]

    def close(self) -> None:
        """Close the underlying connection."""
        self._conn.close()
