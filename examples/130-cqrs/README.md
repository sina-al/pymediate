# 130-cqrs

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/sina-al/pymediate?devcontainer_path=.devcontainer%2F130-cqrs%2Fdevcontainer.json)

Command Query Responsibility Segregation (CQRS) separates operations that change state from
operations that read state. PyMediate does not add a second dispatch API for CQRS: commands
and queries are both `Request` types sent through one mediator. The separation is in their
handlers, data models, and stores.

It builds on the request, notification, dependency, and testing patterns from the preceding examples.

This example uses:

- SQLite as the write store for online transaction processing (OLTP);
- DuckDB as a projected read store for online analytical processing (OLAP);
- a transactional outbox so a committed write is not lost before projection; and
- a checkpoint so callers can wait for the read model when they need read-after-write
  consistency.

## Run

Run these commands from `examples/130-cqrs`:

```bash
uv sync
uv run catalog
```

Sample output:

```text
CreateProduct      -> CreateProductResult(product_id=1, outbox_position=1)
AdjustStock        -> AdjustStockResult(product_id=1, new_stock=7, outbox_position=2)
read model at checkpoint <0-4>, waiting for outbox position 4...
caught up at checkpoint 4
GetProduct         -> ProductView(product_id=1, name='Keyboard', price=49.99, stock=7, in_stock=True, price_tier='standard')
SearchProducts     -> 3 product(s) in stock
GetInventoryReport ->
    budget   count=1 value=1700.0 avg=8.5
    premium  count=1 value=1316.0 avg=329.0
    standard count=1 value=349.93 avg=49.99
```

The first checkpoint varies because the projection worker runs in the background. The final
checkpoint and query results are deterministic: the demo waits until the read model reaches
outbox position 4 before it issues the queries.

## The write path

A command writes the domain row and its outbox record in one SQLite transaction:

```python
conn.execute("BEGIN IMMEDIATE")
conn.execute("INSERT INTO products (name, price, stock) VALUES (?, ?, ?)", ...)
_append_outbox(conn, PRODUCT_CREATED, {...})
conn.execute("COMMIT")
```

Both rows commit or both roll back. The command does not write to DuckDB, so a DuckDB failure
cannot leave the command half-committed across two databases.

Each command result includes an `outbox_position`. A caller that needs to read its own write
can wait until the read model's checkpoint reaches that position. Other callers can accept
the normal delay of eventual consistency.

## The projection path

Command handlers publish `OutboxAppended` after the SQLite transaction commits. The notification
only wakes the worker; it is not the durable record:

```python
class AdjustStockHandler(RequestHandler[AdjustStock]):
    async def __call__(self, request: AdjustStock) -> AdjustStockResult:
        ack = self._store.adjust_stock(request.product_id, request.delta)
        await self._publisher.publish(OutboxAppended(sequence=ack.outbox_position))
        return AdjustStockResult(
            product_id=ack.product.product_id,
            new_stock=ack.product.stock,
            outbox_position=ack.outbox_position,
        )


class WakeProjector(NotificationHandler[OutboxAppended]):
    async def __call__(self, notification: OutboxAppended) -> None:
        self._worker.wake()
```

The worker also polls, so it still finds the outbox row if the in-memory notification is lost.
It reads rows after the current checkpoint, applies a batch to DuckDB, and advances the
checkpoint in the same DuckDB transaction.

The outbox events contain resulting state rather than only deltas. For example,
`StockAdjusted` contains the new stock level. This event shape supports safe replay when the
read model is rebuilt.

## The read path

Query handlers depend on the `ReadModel` protocol. It exposes product lookup, search, and the
inventory report, but not projection batches or checkpoint updates. The projector receives a
separate `ProjectionTarget` protocol.

The projected `ProductView` contains `in_stock` and `price_tier`, which are derived fields that
do not need to be stored in the write model. `GetInventoryReport` groups the projected catalog
by price tier.

## Compare the two stores

The optional benchmark loads the same generated products into SQLite and DuckDB, then sends
the same aggregation through each query handler:

```bash
uv run catalog-benchmark
```

Example from one machine:

```text
  query                     store             role  query time
  GetInventoryReportNaive   SQLite (rows)     OLTP    2525.9 ms
  GetInventoryReport        DuckDB (columns)  OLAP       8.6 ms

  DuckDB is 294x faster on the identical rollup.
```

This is a local demonstration, not a stable performance claim. The times and ratio depend on
hardware, database versions, row count, and operating-system state. The benchmark checks that
both stores return the same aggregation before presenting the comparison.

Pass a row count to change the dataset size:

```bash
uv run catalog-benchmark 5000000
```

## Read the code

| File | What to read |
| --- | --- |
| [`src/catalog/domain.py`](src/catalog/domain.py) | **Start here.** Identify the commands, queries, projected views, and outbox event types. |
| [`src/catalog/write_store.py`](src/catalog/write_store.py) | Follow the SQLite transaction that commits a product change and outbox row together. |
| [`src/catalog/projection.py`](src/catalog/projection.py) | Follow outbox batches from the current checkpoint into the read model. |
| [`src/catalog/read_store.py`](src/catalog/read_store.py) | Compare the query-facing `ReadModel` and projector-facing `ProjectionTarget` protocols. |
| [`src/catalog/handlers.py`](src/catalog/handlers.py) | Compare command, query, and worker-notification responsibilities. |
| [`src/catalog/app.py`](src/catalog/app.py) | See one `Services` collection and one `Mediator` assemble both paths. |
| [`tests/test_cqrs.py`](tests/test_cqrs.py) | Check stale reads, projection, missing products, report equivalence, and the live worker. |
| [`docs/architecture.md`](docs/architecture.md) | Trace transaction boundaries, checkpoint recovery, and the single-process limitation. |

## Details

This is a single-process example with local database files. DuckDB has one writer here: the
projection worker. A production system also needs decisions about schema evolution, outbox
retention, records that repeatedly fail projection, monitoring, and deployment ownership.

## Where next

- Continue with [`900-hexagonal-architecture`](../900-hexagonal-architecture/) to see commands,
  queries, events, adapters, dependency injection, and background work in one application.
- Review [`110-testing`](../110-testing/) for the test boundaries used in this example.
- Read about [requests, responses, and optional CQRS conventions](https://pymediate.sina-al.uk/docs/guide/requests-responses#commands-and-queries-are-optional-conventions).
