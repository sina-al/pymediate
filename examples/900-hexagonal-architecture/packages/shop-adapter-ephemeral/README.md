# Shop ephemeral adapter

`shop-adapter-ephemeral` provides SQLite and process-local implementations of external Shop
capabilities. It powers the zero-infrastructure profile, mediator-first application tests, and full
background journeys that run inside one process.

The package depends on `shop-domain` and `shop-ports`. It does not depend on the application,
bindings, or an executable host.

## What ephemeral means

Most implementations in this package keep observable state in memory and lose it when the process
exits. They preserve the contract that the application needs, including idempotency and message
settlement, but they are not distributed services.

SQLite is the exception to "memory-backed" storage. It remains here because it supplies the local
single-process database profile. The default configuration uses an in-memory database; the gateway
can also use a file path.

Stateless reusable implementations belong in `shop-adapter-common`. Branded PDF rendering belongs
in `shop-adapter-weasyprint` because it has a rendering engine and native dependencies.

## Modules

### `shop.adapters.ephemeral.sqlite`

`SqliteDbGateway` implements the business database ports, append-only domain-event journal,
transactional outbox, and inbox. It uses `aiosqlite`, initializes the example schema, and keeps a
shared in-memory database available for the resource lifetime. The gateway implements both narrow
business database ports and the separate journal port. They are supplied independently to handlers
but share the connection selected by `SqliteUnitOfWork`, so a rollback removes both the state
change and its audit fact.

Schema creation is defined in `sqlite_schema.py`, while `SqliteUnitOfWork` is defined in
`sqlite_unit_of_work.py`. A unit is one-shot and owned by the exact asyncio task that entered it.
Transactions are serialized over the local connection; nested use, sequential reuse, and access
from an inherited child-task context are rejected. Independent reads and relay operations wait for
the active transaction rather than joining it. Atomic identity sequences avoid concurrent
`MAX(id) + 1` allocation.

Outbox and inbox claims carry opaque tokens. Renew, complete, publish, and release statements all
check the token, so a stale task cannot settle work after lease expiry and reclamation.

### `shop.adapters.ephemeral.catalogue`

`EphemeralCatalogue` implements the product-catalogue port with a fixed immutable set of products.
All three profiles use it because a production catalogue service
is out of scope. Its state is process-local and it has no resource lifecycle.

### `shop.adapters.ephemeral.messaging`

`EphemeralMessageBroker` implements publication, competing consumption, visibility leases,
completion, abandonment, lock renewal, repeated delivery, and a dead-letter queue. Visibility
expiry counts toward the delivery threshold, and a stale delivery handle cannot settle a newer
lock. It matches the worker's required semantics closely enough for fast journey tests, but messages
cannot cross a process boundary.

### `shop.adapters.ephemeral.inventory`

`EphemeralInventory` records reservations and releases. Its visible state lets tests verify that
placing and cancelling orders call the correct capability.

### `shop.adapters.ephemeral.payments`

`EphemeralPayments` records charges, refunds, and cancellation compensation. It demonstrates an
external effect without assigning a payment provider to the domain.

### `shop.adapters.ephemeral.mailer`

`ConsoleMailer` records order confirmation, cancellation, refund, and export-ready mail. It
suppresses duplicate effects by idempotency key so an at-least-once queue delivery does not send the
same confirmation or download link twice.

### `shop.adapters.ephemeral.storage`

`EphemeralStorage` stores generated exports, invoices, and statements in process memory and returns
logical URLs. It also suppresses duplicate writes by idempotency key.

## Configuration and lifecycle

`configuration/default.yaml` selects every implementation in this package that has local state.
The cloud profiles still use the ephemeral catalogue, inventory, payment, and mail because those
services are not otherwise modeled. Only `SqliteDbGateway` has a resource lifetime and must be
closed.

## Appropriate use

Use this adapter for local development, application tests, and the complete in-process outbox
journey. Use PostgreSQL and a real or emulated cloud broker when testing concurrent transactions,
cross-process delivery, client-library behavior, redrive configuration, or operational failure modes.

See the [complete Shop guide](../../README.md) for the default profile and end-to-end message path.
