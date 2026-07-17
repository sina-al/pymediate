# 080-cqrs

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/sina-al/pymediate?devcontainer_path=.devcontainer%2F080-cqrs%2Fdevcontainer.json)

How do you separate reads from writes? In PyMediate, **CQRS is a naming convention over
request types, not extra machinery** — commands and queries both subclass `Request` and
dispatch through the same `mediator.send()`. What makes it worth doing is giving each side
**its own store, tuned for what that side does**. This example makes that concrete: the write
side is a **SQLite** table (row-oriented, transactional — OLTP), the read side is a **DuckDB**
table (columnar, built for scan-and-aggregate reads — OLAP), and an event keeps them in sync.

## Run it

```bash
cd examples/080-cqrs
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

`CreateProduct` and `AdjustStock` return just enough to confirm the write. `GetProduct`
returns a `ProductView` with two fields — `in_stock`, `price_tier` — that don't exist on the
write side. And `GetInventoryReport` is a query the write side simply can't answer well: a
roll-up across the whole catalog. That's the split, made visible in one run.

## Two stores, two engines

```python
class WriteStore:
    """The write side: a normalized SQLite table — row-oriented, transactional (OLTP)."""
    def create(self, name: str, price: float, stock: int) -> Product: ...
    def adjust_stock(self, product_id: int, delta: int) -> Product: ...

class ReadStore:
    """The read side: a denormalized DuckDB table — columnar, built for aggregates (OLAP)."""
    def find(self, product_id: int) -> ProductView | None: ...
    def search(self, *, in_stock_only: bool = False) -> list[ProductView]: ...
    def inventory_report(self) -> list[TierSummary]: ...
```

A write touches one product — insert a row, or bump one row's stock. SQLite is a row store,
which keeps a product's fields together: exactly the shape of that access. A `ProductView`
adds `in_stock` and `price_tier` — derived fields a reader wants that the write side has no
reason to store. And the read side's reason to exist is `inventory_report`, an aggregate that
scans every row. DuckDB is a column store, so that scan reads only the columns it needs.
**Two stores, two engines, each picked for what its side actually does.**

## Commands write; queries read; an event connects them

```python
class CreateProductHandler(RequestHandler[CreateProduct]):
    async def __call__(self, request: CreateProduct) -> ProductId:
        product = self._store.create(request.name, request.price, request.stock)
        await self._publisher.publish(ProductCreated(product_id=product.product_id, ...))
        return ProductId(product_id=product.product_id)   # minimal — just the new id

class GetProductHandler(RequestHandler[GetProduct]):
    async def __call__(self, request: GetProduct) -> ProductView:
        return self._store.find(request.product_id)        # rich — the full read model
```

A command handler never touches `ReadStore`, and a query handler never touches `WriteStore`
— each side stays ignorant of the other's storage. The read side (DuckDB) learns what
happened only by subscribing to the events commands publish (`ProductCreatedProjector`,
`StockAdjustedProjector`), the same `publish()` fan-out from [020-events](../020-events/).
The handlers don't know or care which engine backs each store — this example started as two
in-memory dicts, and moving to SQLite and DuckDB changed only the two store classes, not a
line of handler or wiring code.

That last claim — "a query handler never touches `WriteStore`" — is easy to state and easy to
accidentally violate, since `ReadStore` also has to expose `upsert` for the projectors to
call. So query handlers don't depend on `ReadStore` at all; they depend on `ReadModel`, a
`Protocol` with only `find`/`search`/`inventory_report` on it. Projectors depend on the
separate `ReadModelProjector` protocol (`peek`/`upsert`). `ReadStore` implements both — it's
one table underneath — but nothing outside `domain.py` ever holds a reference typed as
`ReadStore`. Give `GetProductHandler` a `ReadModel` and call `.upsert()` on it, and
`mypy --strict`/basedpyright reject it: that method isn't on the type you were handed. The
separation isn't a comment asking nicely; the type checker enforces it.

## The analytical query — and why it's DuckDB

`GetInventoryReport` rolls the catalog up by price tier: for each tier, how many products,
their total inventory value, the average price. It's a full-catalog scan-and-aggregate — the
kind of read the write store would grind through row by row, and the whole reason the read
side is a column store. `benchmark.py` seeds a large synthetic catalog into both engines and
times the identical `GROUP BY` on each:

```bash
uv run catalog-benchmark            # 1,000,000 products
uv run catalog-benchmark 5000000    # more rows, a wider gap
```

```text
Seeding 1,000,000 products into SQLite (OLTP) and DuckDB (OLAP)...
Timing the tier rollup, best of 5 runs...

  engine            role   query time
  SQLite (rows)     OLTP      2033.6 ms
  DuckDB (columns)  OLAP        22.6 ms

  DuckDB is 90x faster on the identical GROUP BY.

  Both return the same rollup, e.g.:
    budget   count=    63,671 value=     16,752,754.05 avg=10.50
    premium  count=   669,222 value=  3,343,301,230.41 avg=199.99
    standard count=   267,107 value=    400,031,767.19 avg=59.95
```

(Exact numbers depend on your machine; the two-orders-of-magnitude gap doesn't.) Same rows,
same query, same answer — the read store isn't cutting a corner to win, it's the right tool
for this read. That gap *is* the argument for keeping a separate read side.

## Wiring: one `Services` collection, one `Mediator`

```python
services = Services()
services.add(CreateProductHandler(write_store, publisher))
services.add(AdjustStockHandler(write_store, publisher))
services.add(GetProductHandler(read_store))
services.add(SearchProductsHandler(read_store))
services.add(InventoryReportHandler(read_store))
services.add(ProductCreatedProjector(read_store))
services.add(StockAdjustedProjector(read_store))
mediator = Mediator(services.provider())
```

Commands, queries, and the projectors that connect them all register on the same collection
and dispatch through the same mediator. There's no second mediator, no parallel dispatch
path — CQRS lives entirely in which store each handler is allowed to touch.

## The files

| File | What it is |
| --- | --- |
| [`src/catalog/domain.py`](src/catalog/domain.py) | **Start here.** The SQLite `WriteStore`, the DuckDB `ReadStore` (with `inventory_report`), the events between them, and the command/query request types. |
| [`src/catalog/handlers.py`](src/catalog/handlers.py) | The command handlers, the query handlers, and the projectors that keep the read side in sync. |
| [`src/catalog/app.py`](src/catalog/app.py) | `build_mediator` and the demo. |
| [`src/catalog/benchmark.py`](src/catalog/benchmark.py) | The OLTP-vs-OLAP micro-benchmark: `uv run catalog-benchmark`. Not a test. |
| [`tests/test_cqrs.py`](tests/test_cqrs.py) | Proves the split on a handful of rows — minimal command responses, the denormalized view, separate store shapes, event-driven updates, the tier rollup: `uv run pytest` → `8 passed`. |

## Small print

- **DuckDB is single-writer and built for analytical reads, not concurrent OLTP writes.**
  That's fine here: only the projectors write to it, one event at a time, and everything else
  reads. Don't read this example as "point your write traffic at DuckDB" — the whole point is
  that the write traffic goes to SQLite.
- **Feeding an OLAP store one row per event is against its grain.** A real projection is
  usually batch-loaded or fed by change-data-capture, not upserted a row at a time. This
  example upserts per-event to stay a runnable, self-contained demo; `benchmark.py` uses
  DuckDB's bulk `COPY` path, which is how you'd actually load it.
- **The projection here is in-process and synchronous** — a dict swapped for a DuckDB table
  in the same call. In production the read side is usually a separate replica or warehouse
  kept in sync asynchronously. The shape of the split is the same either way.
- `LateBoundPublisher` solves a wiring order problem: a command handler needs to publish
  through the `Mediator`, but the `Mediator` doesn't exist until *after* the handlers are
  registered. It's bound to the real mediator once construction finishes — the same pattern
  [050-handler-composition](../050-handler-composition/) uses.

## Where next

- [080-cqrs-sync](../080-cqrs-sync/) — the same command/query split on `pymediate.sync`.
- [020-events](../020-events/) — the `publish()` fan-out this example's projectors build on.
- [040-pipeline-behaviors](../040-pipeline-behaviors/) — a `PipelineBehavior[Query]` that
  caches reads, if you want to add caching on top of this split.
- The docs: [CQRS example](https://pymediate.sina-al.uk/docs/examples/cqrs).
