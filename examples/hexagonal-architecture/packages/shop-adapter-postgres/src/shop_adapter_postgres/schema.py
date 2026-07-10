"""Schema management: create the tables the adapters need."""

from psycopg_pool import ConnectionPool

DDL = """
CREATE TABLE IF NOT EXISTS customers (
    customer_id        TEXT PRIMARY KEY,
    name               TEXT NOT NULL,
    email              TEXT NOT NULL,
    store_credit_cents INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS orders (
    order_id    TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL REFERENCES customers (customer_id),
    items       JSONB NOT NULL,
    status      TEXT NOT NULL,
    placed_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS orders_by_customer ON orders (customer_id, placed_at);
"""


def ensure_schema(pool: ConnectionPool) -> None:
    """Create the tables if they don't exist yet — called once at startup."""
    with pool.connection() as conn:
        conn.execute(DDL)
