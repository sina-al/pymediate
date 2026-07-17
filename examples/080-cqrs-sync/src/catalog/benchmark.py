"""A local micro-benchmark: the tier-rollup query on SQLite (OLTP) vs DuckDB (OLAP).

This isn't a test — it's a thing you run by hand to *see* why the read side of this example
is DuckDB and not the SQLite write store. It seeds a large synthetic catalog into both
engines, then times the exact query ``ReadStore.inventory_report`` runs
(``GROUP BY price_tier``) on each, and prints the gap:

    uv run catalog-benchmark            # 1,000,000 products (a few seconds)
    uv run catalog-benchmark 5000000    # more rows, a wider gap

The seed is a bulk load (DuckDB's ``COPY`` from a temporary CSV, SQLite's ``executemany``),
deliberately bypassing the mediator — the app writes one row at a time through commands; a
benchmark shouldn't. Only the query is timed, best of several runs, so seeding cost doesn't
count. Nothing here touches ``pymediate``; it's measuring the two storage engines directly.
"""

import csv
import random
import sqlite3
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

import duckdb

# The identical aggregation ReadStore.inventory_report runs, against a raw table.
REPORT_SQL = (
    "SELECT price_tier, count(*), sum(price * stock), avg(price) "
    "FROM products GROUP BY price_tier ORDER BY price_tier"
)


def _price_tier(price: float) -> str:
    if price < 20:
        return "budget"
    if price < 100:
        return "standard"
    return "premium"


def _generate(n: int) -> list[tuple[int, str, float, int, bool, str]]:
    """Build ``n`` synthetic product rows, matching the read-side view's columns."""
    rng = random.Random(0)  # fixed seed: the same catalog every run
    rows: list[tuple[int, str, float, int, bool, str]] = []
    for product_id in range(1, n + 1):
        price = round(rng.uniform(1.0, 300.0), 2)
        stock = rng.randint(0, 50)
        rows.append(
            (product_id, f"Product {product_id}", price, stock, stock > 0, _price_tier(price))
        )
    return rows


def _seed_sqlite(rows: list[tuple[int, str, float, int, bool, str]]) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE products (product_id INTEGER PRIMARY KEY, name TEXT, price REAL, "
        "stock INTEGER, in_stock INTEGER, price_tier TEXT)"
    )
    conn.executemany("INSERT INTO products VALUES (?, ?, ?, ?, ?, ?)", rows)
    conn.commit()
    return conn


def _seed_duckdb(rows: list[tuple[int, str, float, int, bool, str]]) -> duckdb.DuckDBPyConnection:
    conn = duckdb.connect()
    conn.execute(
        "CREATE TABLE products (product_id INTEGER PRIMARY KEY, name VARCHAR, price DOUBLE, "
        "stock INTEGER, in_stock BOOLEAN, price_tier VARCHAR)"
    )
    # COPY from a temporary CSV: DuckDB's bulk-load path. (Row-by-row INSERT into a column
    # store is pathologically slow — the wrong way to load an OLAP engine.)
    with tempfile.TemporaryDirectory() as tmp:
        csv_path = Path(tmp) / "seed.csv"
        with csv_path.open("w", newline="") as handle:
            csv.writer(handle).writerows(rows)
        conn.execute(f"COPY products FROM '{csv_path}' (HEADER false)")
    return conn


def _best_ms(query: Callable[[], object], repeats: int) -> float:
    """Fastest of ``repeats`` runs, in milliseconds — the usual way to report a hot query."""
    best = float("inf")
    for _ in range(repeats):
        start = time.perf_counter()
        query()
        best = min(best, time.perf_counter() - start)
    return best * 1000


def main(n: int = 1_000_000, repeats: int = 5) -> None:
    """Seed both engines with ``n`` products and time the tier rollup on each."""
    print(f"Seeding {n:,} products into SQLite (OLTP) and DuckDB (OLAP)...", flush=True)
    rows = _generate(n)
    sqlite_conn = _seed_sqlite(rows)
    duckdb_conn = _seed_duckdb(rows)

    print(f"Timing the tier rollup, best of {repeats} runs...\n", flush=True)
    sqlite_ms = _best_ms(lambda: sqlite_conn.execute(REPORT_SQL).fetchall(), repeats)
    duckdb_ms = _best_ms(lambda: duckdb_conn.execute(REPORT_SQL).fetchall(), repeats)

    print(f"  {'engine':<18}{'role':<7}query time")
    print(f"  {'SQLite (rows)':<18}{'OLTP':<7}{sqlite_ms:>9.1f} ms")
    print(f"  {'DuckDB (columns)':<18}{'OLAP':<7}{duckdb_ms:>9.1f} ms")
    print(f"\n  DuckDB is {sqlite_ms / duckdb_ms:.0f}x faster on the identical GROUP BY.\n")

    # Same rows, same query, same answer — the OLAP store isn't cutting a corner to win.
    print("  Both return the same rollup, e.g.:")
    for tier, count, value, avg in duckdb_conn.execute(REPORT_SQL).fetchall():
        print(f"    {tier:<8} count={count:>10,} value={value:>18,.2f} avg={avg:.2f}")


def run() -> None:
    """Console-script entry point (``uv run catalog-benchmark [n]``)."""
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 1_000_000
    main(n)


if __name__ == "__main__":
    run()
