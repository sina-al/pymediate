# Shop PostgreSQL adapter

`shop-adapter-postgres` implements the Shop's relational persistence contracts with Psycopg and an
asynchronous connection pool. The AWS and Azure profiles both select it.

The package depends on `shop-domain` and `shop-ports`. It does not import the application handlers,
bindings, FastAPI, worker, or cloud adapters.

## Public implementations

### `PostgresDbGateway`

The gateway implements the focused database protocols used by orders, customers, invoices, and
statements. It also implements the append-only domain-event journal, transactional outbox relay
source, outbox writer, and inbox deduplication contracts.

One class may implement many protocols because one PostgreSQL schema naturally supplies those
capabilities. Handlers still receive a narrow protocol, so they cannot call unrelated gateway
methods.

The gateway owns an `AsyncConnectionPool`. Reads outside a transaction and relay/inbox operations
lease independent connections. Order, invoice, and statement identifiers use PostgreSQL identities
rather than application-side `MAX(id) + 1` calculations.

Mutable order and customer reads use row locks inside a unit of work. Invoice order IDs have a
database uniqueness constraint, and schema startup is synchronized so concurrent resource
resolution cannot initialize the pool or schema more than once.

### `PostgresUnitOfWork`

The unit of work leases one connection and binds it to the exact asynchronous task for the
transaction duration. Gateway calls inside that block use the bound connection. A copied context in
a child task cannot use the transaction. On exit the unit commits or rolls back, releases the
connection, and clears task-local state.

Nested use and reuse are rejected with a clear error. A handler controls the transaction block, so
the adapter never holds a transaction open around an external payment, mail, or storage call unless
the handler explicitly places that call inside the block.

`PostgresDbGateway` implements the journal alongside the narrow business gateways, but the ports
remain separate in handler signatures. Both resolve the task-local leased connection inside a unit
of work. This makes business state, audit facts, and any outbox contracts atomic without coupling
their types or identifiers.

## Schema responsibilities

For a self-contained example, the adapter creates the required tables on first connection. The
schema covers customers, orders, invoices, statements, domain-event journal records, outbox
messages, and inbox messages.

Outbox and inbox rows store opaque lease tokens; every renewal and settlement checks that token and
the current expiry. The implementation is divided into `gateway.py`, `schema.py`, and
`unit_of_work.py`. The package root continues to export `PostgresDbGateway` and
`PostgresUnitOfWork` as its stable surface.

A production application would normally move schema changes into a migration system. That choice
does not change the gateway protocols or application handlers.

## Configuration and lifecycle

`configuration/aws.yaml` and `configuration/azure.yaml` create `PostgresDbGateway` as a resource
using `SHOP_POSTGRES_URL`. `PostgresUnitOfWork` is a factory because each use-case invocation needs
a fresh transaction context.

The host's `Wiring` lifecycle opens the pool and closes it on shutdown. No destructor or manual
host cleanup is required.

## Testing

Application tests normally use SQLite for speed. Opt-in PostgreSQL Testcontainers tests cover
concurrent startup, overlapping row locks, rollback isolation, independent relay access, generated
identities, task ownership, and stale lease settlement using the actual Psycopg pool. A separate
opt-in journey exercises PostgreSQL with S3-compatible storage.

See the [complete Shop guide](../../README.md) for the cloud profiles and transaction model.
