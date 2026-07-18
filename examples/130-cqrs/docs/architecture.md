# Architecture: the transactional outbox and the projection worker

The [README](../README.md) shows what this example does. This note explains how the read side
stays correct and how each local component maps to a larger deployment.

> **This is an illustrative, single-process demo.** It runs a local SQLite file and a local
> DuckDB file inside one Python process. The *shape* of the design is what transfers to
> production; the specific engines and the in-process worker are stand-ins. The
> ["Real-world analogues"](#real-world-analogues) section maps each one.

## The problem: don't write two databases in one command

The read side (DuckDB) has to receive every write. One approach is to make the
command handler write both stores:

```text
CreateProduct
  ├── INSERT into SQLite   ✅ committed
  └── INSERT into DuckDB   ❌ fails
```

Now the two stores disagree and this request has no durable record from which to reconcile
them. This is the **dual-write problem**: whichever write runs second can fail after the first
has committed. Coordinating them with a distributed transaction adds another protocol and
requires both engines to support it.

The old version of this example had a subtler form of the same bug: it projected to DuckDB in
a *synchronous event handler* that ran inside the command's `send()` call. SQLite was already
committed by then, so a DuckDB failure left the read side behind with no retry — the second
write was still inside the command's failure boundary.

## The fix: a transactional outbox

Write **one** database in the command, and record the fact you'll need to project as a row in
that same database, in the same transaction:

```text
CreateProduct
  └── one SQLite transaction
        ├── INSERT into products   (the write model)
        └── INSERT into outbox     (the event to project later)
      commit
```

Either both rows land or neither does — it's a single local transaction, no second engine
involved (`write_store.py`, `WriteStore.create`). The `outbox` table is an ordered, durable log
of everything the read side still needs to catch up on. A separate worker reads it later.

The outbox's `sequence` column is `INTEGER PRIMARY KEY AUTOINCREMENT`. Positions increase for
committed rows. Gaps can appear if rows are deleted; the projector requires an ordered
position, not consecutive numbers.

## The projection worker

A single worker owns the read side (`projection.py`). Its cycle:

1. read the projector's `last_sequence` from DuckDB (the **checkpoint**);
2. read the next batch of outbox rows where `sequence > last_sequence`;
3. in **one DuckDB transaction**: apply every event, then advance the checkpoint to the last
   event's sequence;
4. commit.

```text
outbox (SQLite)                      read model (DuckDB)
  seq 5  ProductCreated  ─┐          BEGIN
  seq 6  StockAdjusted   ─┼─ batch ─▶  apply 5, 6, 7
  seq 7  ProductCreated  ─┘            UPDATE checkpoint = 7
                                     COMMIT
```

`Projector.drain()` is a plain synchronous method — read checkpoint, read a batch, apply,
repeat until the outbox is exhausted. `ProjectionWorker` runs a loop around it: drain, then
wait for a notification or a poll timeout, then drain again.

### Logical update vs physical write

Every command produces a *logical* projection update, but DuckDB doesn't need a transaction per
command. Because `drain()` applies a whole batch in one transaction, a burst of ten commands
that are all pending when the worker wakes becomes **one** physical DuckDB write of ten
projection updates. Column stores generally perform better with fewer batch writes than with
many individual writes, so the worker batches pending updates.

### The wake-up only reduces latency

After a command commits, its handler publishes `OutboxAppended` through the mediator. A single
event handler, `WakeProjector`, sets the worker's wake flag. The durable path is the outbox and
the poll. If the process crashes and the in-memory notification is lost, the next poll still
finds the row. Publishing the notification can reduce the delay before the next projection.

Notice what the command handler *doesn't* know: it announces `OutboxAppended` and returns. It
has no reference to the worker, the projector, or DuckDB. Swap the worker for a Kafka producer
or a separate projection service and the command handler is unchanged.

## Why the checkpoint makes recovery safe

Because the batch apply and the checkpoint advance commit together, there are two crash cases:

- **Crash before the DuckDB commit** — neither the projection changes nor the checkpoint is
  committed. On restart the worker reads the same batch. The transaction applies it once.
- **Crash after the DuckDB commit** — both landed. On restart the worker resumes after the
  checkpoint and never re-applies.

The target changes and checkpoint therefore move atomically for this single ordered worker.
The event shapes are also idempotent: `ProductCreated` upserts the full view, and
`StockAdjusted` carries the resulting stock level rather than a delta. That makes an explicit
replay or rebuild safe. This example does not trim the outbox, so it can rebuild the read model
from the beginning.

## Eventual consistency, made explicit

The projection runs *after* the command commits, so the read side is eventually consistent:

```text
CreateProduct returns          (SQLite committed, outbox position 42)
GetProduct runs immediately    (DuckDB may not have product 42 yet)
```

Rather than hide this, the example surfaces it. Commands return their `outbox_position`, and a
caller that needs to read its own write waits until the read model's checkpoint reaches that
position — `wait_until_caught_up(read_store, position)` in `projection.py`. The demo prints the
checkpoint catching up; a test asserts on it with a bounded timeout.

## The single-process limitation

DuckDB's file concurrency model allows **one read-write process**. Multiple processes can open
the same file read-only, but only when no process is writing it. This example uses one process
and one asyncio task as the sole writer. Do not run several web-server workers that each open
this DuckDB file for writing.

For a multi-process deployment, put a process boundary around the DuckDB owner:

```text
Command app  ──▶  SQLite outbox  ──▶  DuckDB owner process
                                       ├── projection worker (sole writer)
                                       └── query API over HTTP/IPC
```

or replace DuckDB with a client-server read database.

## Real-world analogues

| This demo | A production system |
| --- | --- |
| Local **SQLite** write file | A transactional OLTP database — Postgres, MySQL, or a hosted SQLite like Turso/libSQL |
| The `outbox` table | Still an outbox table in the OLTP database — the pattern is identical at any scale |
| Local **DuckDB** read file | A columnar analytical store — Snowflake, BigQuery, ClickHouse, Redshift, or DuckDB/MotherDuck |
| In-process **projection worker** (asyncio task) | Change-data-capture (Debezium, Kafka Connect) or a dedicated projection service consuming the outbox |
| `OutboxAppended` in-memory notification | A message broker (Kafka, SQS, NATS), or change-data capture reading the log |
| Temp files, one process | Durable managed storage; the read store owned by one writer, queried by many |

The command/query split, outbox, checkpoint, and idempotent event shapes also apply to larger
systems. A production design additionally needs policies for schema evolution, outbox
retention, records that repeatedly fail projection, monitoring, and service ownership.
