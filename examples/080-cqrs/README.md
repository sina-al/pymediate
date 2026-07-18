# 080-cqrs

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/sina-al/pymediate?devcontainer_path=.devcontainer%2F080-cqrs%2Fdevcontainer.json)

How do you separate reads from writes — and keep the read side correct? In PyMediate, **CQRS is
a naming convention over request types, not extra machinery**: commands and queries both
subclass `Request` and dispatch through the same `mediator.send()`. What makes it worth doing is
giving each side its own store, tuned for what it does — a **SQLite** write side (row-oriented,
transactional — OLTP) and a **DuckDB** read side (columnar, built for scan-and-aggregate — OLAP).
The hard part is syncing them without a fragile dual write. This example does it the canonical
way: a **transactional outbox** and a **background projection worker**.

## Run it

```bash
cd examples/080-cqrs
uv sync
uv run catalog
```

```text
CreateProduct      -> CreateProductResult(product_id=1, outbox_position=1)
AdjustStock        -> AdjustStockResult(product_id=1, new_stock=7, outbox_position=2)
read model at checkpoint 4, waiting for outbox position 4...
caught up at checkpoint 4
GetProduct         -> ProductView(product_id=1, name='Keyboard', price=49.99, stock=7, in_stock=True, price_tier='standard')
SearchProducts     -> 3 product(s) in stock
GetInventoryReport ->
    budget   count=1 value=1700.0 avg=8.5
    premium  count=1 value=1316.0 avg=329.0
    standard count=1 value=349.93 avg=49.99
```

Commands return only what the caller needs — an id, plus the **outbox position** so a reader can
tell when its write has landed. Then the demo *waits* for the read model to catch up to that
position before querying: the read side is eventually consistent, and this makes it explicit
rather than hiding it. `GetProduct` returns a `ProductView` with two fields — `in_stock`,
`price_tier` — that don't exist on the write side. And `GetInventoryReport` is the analytical
roll-up the read side exists for.

## The one write that matters: domain row + outbox, atomically

The command never writes two databases. It writes **one** SQLite transaction containing the
domain row *and* an outbox row describing what changed:

```python
# write_store.py
conn.execute("BEGIN IMMEDIATE")
conn.execute("INSERT INTO products (name, price, stock) VALUES (?, ?, ?)", ...)
_append_outbox(conn, PRODUCT_CREATED, {...})   # the event to project later
conn.execute("COMMIT")                          # both rows, or neither
```

Either both land or neither does — there's no second engine in this write path, so there's no
dual-write failure mode. The read model is built **afterward**, from the outbox, by a separate
worker. That decoupling is the whole point: the DuckDB write is no longer inside the command's
failure boundary. (The naive alternative — writing DuckDB inside the command, or in a
synchronous event handler during `send()` — is exactly the bug this avoids; see
[`docs/architecture.md`](docs/architecture.md).)

## Commands write; a worker projects; queries read

```python
class CreateProductHandler(RequestHandler[CreateProduct]):
    async def __call__(self, request: CreateProduct) -> CreateProductResult:
        ack = self._store.create(request.name, request.price, request.stock)   # SQLite + outbox
        await self._publisher.publish(OutboxAppended(sequence=ack.outbox_position))  # just a nudge
        return CreateProductResult(product_id=ack.product.product_id, outbox_position=ack.outbox_position)

class WakeProjector(EventHandler[OutboxAppended]):
    async def __call__(self, event: OutboxAppended) -> None:
        self._worker.wake()          # ring the bell — nothing more
```

The command handler doesn't know the worker exists; it just announces `OutboxAppended`. The
`WakeProjector` event handler translates that to a nudge — and does **only** that. The durable
path is the outbox itself: the worker (`projection.py`) polls it, applies each batch to DuckDB in
one transaction, and advances a checkpoint. Drop the nudge entirely and the read side still
catches up on the next poll. Query handlers, meanwhile, depend on `ReadModel` — the narrow
read-only slice of the DuckDB store — so a query handler can't advance the checkpoint or apply a
batch. The type checker enforces that split; it isn't a comment asking nicely.

The full pattern — the checkpoint, crash recovery, idempotent events, eventual consistency, and
DuckDB's single-writer limitation — is written up in [`docs/architecture.md`](docs/architecture.md).

## The analytical query — and why it's DuckDB

`GetInventoryReport` rolls the catalog up by price tier: per tier, how many products, their total
inventory value, the average price. It's a full-catalog scan-and-aggregate — the read the write
store would grind through row by row, and the whole reason the read side is a column store.
`benchmark.py` seeds a large synthetic catalog into both engines and times the identical rollup
**through the mediator** — the naive query against SQLite, the analytical one against DuckDB:

```bash
uv run catalog-benchmark            # 1,000,000 products
uv run catalog-benchmark 5000000    # more rows, a wider gap
```

```text
Seeding 1,000,000 products into SQLite (OLTP) and DuckDB (OLAP)...
Timing the tier rollup through the mediator, best of 5 runs...

  query                     store             role  query time
  GetInventoryReportNaive   SQLite (rows)     OLTP    2525.9 ms
  GetInventoryReport        DuckDB (columns)  OLAP       8.6 ms

  DuckDB is 294x faster on the identical rollup.

  Both return the same rollup, e.g.:
    budget   count=    63,671 value=     16,752,754.05 avg=10.50
    premium  count=   669,222 value=  3,343,301,230.41 avg=199.99
    standard count=   267,107 value=    400,031,767.19 avg=59.95
```

(Exact numbers depend on your machine; the two-orders-of-magnitude gap doesn't.) Same rows, same
query, same answer — the read store isn't cutting a corner to win, it's the right tool for this
read. That gap *is* the argument for keeping a separate read side.

## Wiring: one `Services` collection, one `Mediator`

```python
services = Services()
services.add(CreateProductHandler(write_store, publisher))
services.add(AdjustStockHandler(write_store, publisher))
services.add(GetProductHandler(read_store))
services.add(SearchProductsHandler(read_store))
services.add(InventoryReportHandler(read_store))
services.add(NaiveInventoryReportHandler(write_store))   # the benchmark's OLTP baseline
services.add(WakeProjector(worker))
mediator = Mediator(services.provider())
```

Commands, queries, and the wake-up handler all register on the same collection and dispatch
through the same mediator. There's no second mediator and no parallel dispatch path — CQRS lives
in which store each handler is allowed to touch, and the outbox worker sits off to the side.

## The files

| File | What it is |
| --- | --- |
| [`src/catalog/domain.py`](src/catalog/domain.py) | **Start here.** The commands, queries, value types, and the outbox vocabulary — no I/O. |
| [`src/catalog/write_store.py`](src/catalog/write_store.py) | The SQLite write store: the atomic domain-row-plus-outbox transaction. |
| [`src/catalog/read_store.py`](src/catalog/read_store.py) | The DuckDB read model and its checkpoint, behind `ReadModel` / `ProjectionTarget` protocols. |
| [`src/catalog/projection.py`](src/catalog/projection.py) | The projector (`drain()`) and the background worker that loops it. |
| [`src/catalog/handlers.py`](src/catalog/handlers.py) | Command handlers, query handlers, and the `WakeProjector`. |
| [`src/catalog/app.py`](src/catalog/app.py) | `build_app` and the demo. |
| [`src/catalog/benchmark.py`](src/catalog/benchmark.py) | The OLTP-vs-OLAP benchmark through the mediator: `uv run catalog-benchmark`. Not a test. |
| [`tests/test_cqrs.py`](tests/test_cqrs.py) | Proves the split on a handful of rows: `uv run pytest` → `9 passed`. |
| [`docs/architecture.md`](docs/architecture.md) | The deep dive: outbox, checkpoint, recovery, and real-world analogues. |

## Small print

- **This is an illustrative, single-process demo** using a local SQLite file and a local DuckDB
  file. The design transfers; the engines and the in-process worker are stand-ins.
  [`docs/architecture.md`](docs/architecture.md) maps each one to its production analogue
  (Postgres/Turso, Snowflake/ClickHouse, Debezium/Kafka Connect).
- **DuckDB is single-writer and built for analytical reads, not concurrent OLTP writes.** Here
  only the projection worker writes it, one batch at a time, and everything else reads. Don't
  read this as "point write traffic at DuckDB" — write traffic goes to SQLite.
- **The read side is eventually consistent.** A command commits and returns before the worker has
  projected it. Commands hand back an `outbox_position`; a caller that needs read-your-writes
  waits until the read model's checkpoint passes it.

## Where next

- [020-events](../020-events/) — the `publish()` fan-out the wake-up nudge is built on.
- [040-pipeline-behaviors](../040-pipeline-behaviors/) — a `PipelineBehavior[Query]` that caches
  reads, if you want to add caching on top of this split.
- The docs: [CQRS example](https://pymediate.sina-al.uk/docs/examples/cqrs).
