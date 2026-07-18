# Audit journal

The Shop records selected local business state changes as typed domain events. The journal is durable
business history, separate from operational logs and separate from integration messages sent to
workers.

This guide explains why that extra record exists, what it proves, and what it does not prove.

## Three records with different consumers

| Record | Question answered | Consumer and retention |
| --- | --- | --- |
| Domain event | What local business fact was committed? | Internal history and safe projections; retained according to audit policy. |
| Integration event | What versioned contract should another process handle? | Worker registry; retained according to delivery policy. |
| Structured log | What happened while code executed? | Operators and observability systems; retained according to logging policy. |

Similar fields do not make these records interchangeable. Changing an internal audit projection
must not silently change a worker contract. Moving or renaming a Python domain class must not break
messages already waiting in Amazon Simple Queue Service (SQS) or Azure Service Bus.

## Why logs are insufficient

Logs describe execution. A request can start, retry, fail, or be sampled. Log retention and access
are usually operational concerns, and logs may intentionally omit customer identifiers and request
payloads.

The journal instead records a bounded, explicit business fact after a rule has accepted a state
transition. `OrderPlacedEvent`, `StoreCreditAdjustedEvent`, and the other event classes own:

- a stable business name and schema version;
- a typed aggregate reference;
- a primitive JavaScript Object Notation (JSON)-compatible payload.

The handler passes the complete event to `DomainEventJournal`. It cannot provide one event name
with an unrelated aggregate string or second payload.

## Why the append is inside the transaction

The state update and journal append use the same task-bound database transaction:

```python
async with self._unit:
    customer = await self._database.get_customer(request.customer_id)
    credited = customer.add_store_credit(request.amount_pence)
    await self._database.replace_customer(credited)
    await self._journal.append(
        StoreCreditAdjustedEvent(
            credited.customer_id,
            request.amount_pence,
            credited.store_credit_pence,
        )
    )
```

Appending after commit could lose the evidence if the process stopped between the two operations.
Appending before an eventual rollback could retain a fact that never became true. Sharing the
transaction avoids both outcomes.

The journal remains a separate port even though the configured SQLite or PostgreSQL object also
implements the database gateway. The dependencies describe different capabilities. Combining
their implementation allows them to share the current transaction without pretending that every
repository operation is an audit operation.

## Why this is not event sourcing

Orders, customers, invoices, and statements are loaded from current-state tables. The application
does not replay journal entries to reconstruct an entity. The journal can therefore evolve as an
audit and projection source without becoming the persistence model for every domain object.

Likewise, the application does not use `mediator.publish()` to populate the journal. An in-process
event handler would run outside the explicit state-change transaction unless additional machinery
recreated that boundary. The direct append is intentionally visible in the use case.

## Safe external history

Raw journal payloads are internal. A payload may contain fields suitable for trusted audit access
but unsuitable for a customer-facing API, and future event versions may add fields that an old API
never intended to expose.

`GetOrderHistoryRequest` reads the journal and projects only allowlisted
`(event_type, schema_version)` pairs into explicit response fields. Unknown event types and newer
versions are omitted rather than interpreted with an older payload assumption. The FastAPI route
then maps that application response to its Pydantic data-transfer object. Production deployments must additionally
authenticate the caller and authorize access to the requested order.

The example intentionally has no generic HTTP endpoint returning arbitrary journal records.

## Domain events are not queue messages

Creating an order records one internal `orders.order-placed` domain event. It also creates two
independent integration events:

- `shop.orders.order-confirmation-requested`;
- `shop.invoices.invoice-requested`.

One local fact can require several external actions, while another auditable fact may require no
background action. The contracts therefore have independent names, versions, UUIDs, payloads, and
retention rules. There is no generic domain-event-to-integration-event converter.

## What an event proves

A journal event proves that its local state transition committed. It does not automatically prove
that a later external call succeeded.

For example, cancellation and refund record the Shop's new order state before their inline
payment, inventory, or mail effects finish. If one of those calls fails, the journal still describes
the committed local state; it is not a receipt from the remote provider. Create order avoids
emitting invoice or confirmation work for an ordinary declined payment and performs best-effort
in-process compensation if a later local transaction fails, but a process stop can still interrupt
that compensation. These are distributed workflow boundaries, not problems an audit table can
solve.

A production refund flow should model pending and completed refund states, use idempotent payment
commands, and durably resume after failures. The example's `todo/restate-refund-workflow.md` captures
the planned human-approval and durable-workflow version. Until that is implemented, consumers must
interpret refund history as the Shop's recorded state rather than proof of external settlement.

## What not to copy by default

An application does not need a domain-event journal merely because it uses request handlers. Add
one when durable business history, regulated evidence, or explicit historical projections justify
the extra schema and transaction work. Operational request logging should remain a separate
concern.
