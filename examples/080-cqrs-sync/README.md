# 080-cqrs-sync

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/sina-al/pymediate?devcontainer_path=.devcontainer%2F080-cqrs-sync%2Fdevcontainer.json)

The synchronous mirror of [080-cqrs](../080-cqrs/), on `pymediate.sync`. Same split: commands
write through a SQLite `WriteStore` (row-oriented, OLTP) and announce what changed; queries
read a denormalized DuckDB `ReadStore` (columnar, OLAP) kept in sync by subscribing to those
announcements — one `Mediator`, two stores, two engines.

## Run it

```bash
cd examples/080-cqrs-sync
uv sync
uv run catalog
```

```text
CreateProduct      -> ProductId(product_id=1)
AdjustStock        -> StockAdjustedResult(product_id=1, new_stock=7)
GetProduct         -> ProductView(product_id=1, name='Keyboard', price=49.99, stock=7, in_stock=True, price_tier='standard')
SearchProducts     -> 3 product(s) in stock
GetInventoryReport ->
    budget   count=1 value=1700.0 avg=8.5
    premium  count=1 value=1316.0 avg=329.0
    standard count=1 value=349.93 avg=49.99
```

## What changes from the async version

Only the API import and the mechanics — the split itself is identical:

```python
# domain.py
from pymediate.sync import Event, Mediator, Request

# handlers.py
class CreateProductHandler(RequestHandler[CreateProduct]):
    def __call__(self, request: CreateProduct) -> ProductId:   # no async
        product = self._store.create(request.name, request.price, request.stock)
        self._publisher.publish(ProductCreated(product_id=product.product_id, ...))  # no await
        return ProductId(product_id=product.product_id)
```

Every store, event, command, query, and projector in [`domain.py`](src/catalog/domain.py)
and [`handlers.py`](src/catalog/handlers.py) is the same shape as the async twin, minus
`async`/`await`.

## The analytical query and the benchmark

`GetInventoryReport` rolls the catalog up by price tier — the scan-and-aggregate read the
DuckDB read side exists for. [`benchmark.py`](src/catalog/benchmark.py) seeds a large synthetic
catalog into both engines and times the identical `GROUP BY` on each:

```bash
uv run catalog-benchmark            # 1,000,000 products
```

```text
  engine            role   query time
  SQLite (rows)     OLTP      2033.6 ms
  DuckDB (columns)  OLAP        22.6 ms

  DuckDB is 90x faster on the identical GROUP BY.
```

(Numbers vary by machine; the gap is the point.) See [080-cqrs](../080-cqrs/) for the full
walkthrough of why the read side is DuckDB and not the SQLite write store.

## The files

| File | What it is |
| --- | --- |
| [`src/catalog/domain.py`](src/catalog/domain.py) | **Start here.** The SQLite `WriteStore`, the DuckDB `ReadStore` (with `inventory_report`), the events between them, and the command/query request types. |
| [`src/catalog/handlers.py`](src/catalog/handlers.py) | The command handlers, the query handlers, and the projectors that keep the read side in sync. |
| [`src/catalog/app.py`](src/catalog/app.py) | `build_mediator` and the demo. |
| [`src/catalog/benchmark.py`](src/catalog/benchmark.py) | The OLTP-vs-OLAP micro-benchmark: `uv run catalog-benchmark`. Not a test. |
| [`tests/test_cqrs.py`](tests/test_cqrs.py) | Proves the split on a handful of rows: `uv run pytest` → `8 passed`. |

## Where next

- [080-cqrs](../080-cqrs/) — the async default, with the full explanation of the split.
- [020-events-sync](../020-events-sync/) — the `publish()` fan-out this example's projectors
  build on, on `pymediate.sync`.
- The docs: [CQRS example](https://pymediate.sina-al.uk/docs/examples/cqrs).
