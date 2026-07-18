"""A local benchmark: the tier rollup answered by SQLite (OLTP) vs DuckDB (OLAP).

This is not a test. Run it to compare the read-side DuckDB query with the same aggregation on
the SQLite write store. It measures **through the application**: both timed
reads go through ``mediator.send``, hitting the real query handlers.

    uv run catalog-benchmark            # 1,000,000 products (a few seconds)
    uv run catalog-benchmark 5000000    # more rows

- ``GetInventoryReportNaive`` → the naive handler → the SQLite write store (row scan).
- ``GetInventoryReport``      → the analytical handler → the DuckDB read model (column scan).

The catalog is **bulk-loaded** into both engines first (SQLite ``executemany``, DuckDB ``COPY``
from a temporary CSV) — a backfill shortcut, not the per-command outbox path the app uses.
Loading a million rows one command at a time would be the wrong thing to time. Only the two
queries are timed, best of several runs, so seeding cost doesn't count.
"""

import asyncio
import csv
import random
import sqlite3
import sys
import tempfile
import time
from collections.abc import Awaitable, Callable
from pathlib import Path

import duckdb

from .app import build_app
from .domain import GetInventoryReport, GetInventoryReportNaive, Product, project


def _generate(n: int) -> list[Product]:
    """Build ``n`` synthetic products with a fixed seed — the same catalog every run."""
    rng = random.Random(0)
    products: list[Product] = []
    for product_id in range(1, n + 1):
        price = round(rng.uniform(1.0, 300.0), 2)
        stock = rng.randint(0, 50)
        products.append(Product(product_id, f"Product {product_id}", price, stock))
    return products


def _seed_sqlite(database: Path, products: list[Product]) -> None:
    """Bulk-load the write model. (The ``outbox`` table is created later by ``WriteStore``.)"""
    conn = sqlite3.connect(database)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS products (product_id INTEGER PRIMARY KEY, "
        "name TEXT NOT NULL, price REAL NOT NULL, stock INTEGER NOT NULL)"
    )
    conn.executemany(
        "INSERT INTO products (product_id, name, price, stock) VALUES (?, ?, ?, ?)",
        [(p.product_id, p.name, p.price, p.stock) for p in products],
    )
    conn.commit()
    conn.close()


def _seed_duckdb(database: Path, products: list[Product]) -> None:
    """Bulk-load the read model via DuckDB's ``COPY`` path, and mark it fully caught up.

    Row-by-row ``INSERT`` is not representative of a column-store backfill, so this benchmark
    uses DuckDB's bulk ``COPY`` operation.
    """
    views = [project(p) for p in products]
    conn = duckdb.connect(str(database))
    conn.execute(
        "CREATE TABLE IF NOT EXISTS product_view (product_id INTEGER PRIMARY KEY, "
        "name VARCHAR, price DOUBLE, stock INTEGER, in_stock BOOLEAN, price_tier VARCHAR)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS projection_checkpoint "
        "(projection_name VARCHAR PRIMARY KEY, last_sequence BIGINT NOT NULL)"
    )
    with tempfile.TemporaryDirectory() as csv_dir:
        csv_path = Path(csv_dir) / "seed.csv"
        with csv_path.open("w", newline="") as handle:
            writer = csv.writer(handle)
            for view in views:
                writer.writerow(
                    [
                        view.product_id,
                        view.name,
                        view.price,
                        view.stock,
                        view.in_stock,
                        view.price_tier,
                    ]
                )
        conn.execute(f"COPY product_view FROM '{csv_path}' (HEADER false)")
    conn.execute(
        "INSERT INTO projection_checkpoint VALUES ('product_view', ?) ON CONFLICT DO NOTHING",
        [len(views)],
    )
    conn.close()


async def _best_ms(query: Callable[[], Awaitable[object]], repeats: int) -> float:
    """Fastest of ``repeats`` runs, in milliseconds — the usual way to report a hot query."""
    best = float("inf")
    for _ in range(repeats):
        start = time.perf_counter()
        await query()
        best = min(best, time.perf_counter() - start)
    return best * 1000


async def main(n: int = 1_000_000, repeats: int = 5) -> None:
    """Seed both engines with ``n`` products and time the tier rollup on each, via the app."""
    print(f"Seeding {n:,} products into SQLite (OLTP) and DuckDB (OLAP)...", flush=True)
    products = _generate(n)
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        _seed_sqlite(directory / "write.sqlite", products)
        _seed_duckdb(directory / "read.duckdb", products)
        app = build_app(directory)
        try:
            print(f"Timing the tier rollup through the mediator, best of {repeats} runs...\n")
            naive_ms = await _best_ms(lambda: app.mediator.send(GetInventoryReportNaive()), repeats)
            olap_ms = await _best_ms(lambda: app.mediator.send(GetInventoryReport()), repeats)
            naive_report = await app.mediator.send(GetInventoryReportNaive())
            olap_report = await app.mediator.send(GetInventoryReport())
            if naive_report != olap_report:
                raise RuntimeError("SQLite and DuckDB returned different inventory reports")

            rows = [
                ("GetInventoryReportNaive", "SQLite (rows)", "OLTP", naive_ms),
                ("GetInventoryReport", "DuckDB (columns)", "OLAP", olap_ms),
            ]
            print(f"  {'query':<26}{'store':<18}{'role':<6}query time")
            for query_name, store, role, ms in rows:
                print(f"  {query_name:<26}{store:<18}{role:<6}{ms:>8.1f} ms")
            print(f"\n  DuckDB is {naive_ms / olap_ms:.0f}x faster on the identical rollup.\n")

            # Both stores contain the same generated rows and return the same aggregation.
            print("  Both return the same rollup, e.g.:")
            for tier in olap_report:
                print(
                    f"    {tier.price_tier:<8} count={tier.product_count:>10,} "
                    f"value={tier.inventory_value:>18,.2f} avg={tier.avg_price:.2f}"
                )
        finally:
            app.close()


def run() -> None:
    """Console-script entry point (``uv run catalog-benchmark [n]``)."""
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 1_000_000
    asyncio.run(main(n))


if __name__ == "__main__":
    run()
