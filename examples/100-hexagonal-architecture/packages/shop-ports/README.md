# Shop ports

`shop-ports` defines the capabilities the application and worker require from infrastructure. It
also owns the durable envelopes exchanged by independently running processes. The package depends
only on `shop-domain`; it does not import `shop-application`, Dependency Injector, a host, or a
concrete adapter.

Ports are runtime-checkable protocols. Static analysis checks adapter signatures, while the
composition root can reject a configured object that does not provide the required methods.

## Use-case-specific contracts

Persistence protocols are intentionally narrow. `CreateOrderDbGateway`, `RefundOrderDbGateway`,
and `ExportOrdersDbGateway` are separate even though one SQLite or PostgreSQL object implements
all of them. A handler therefore receives only the operations its use case needs. Adding a refund
query does not expand the persistence surface visible during order creation.

The feature modules contain:

- `shop.ports.customers`: insert, load, update, and delete contracts for opening, crediting, and
  closing customer accounts, plus the cross-feature `CustomerOpenOrders` question;
- `shop.ports.orders`: catalogue, database, inventory, payment, mail, export storage, and outbox
  contracts owned by individual order operations;
- `shop.ports.invoices`: idempotent invoice rendering, storage, and persistence;
- `shop.ports.statements`: monthly order streaming, exchange rates, rendering, storage, and
  persistence.

Customer persistence has explicit existence semantics. Inserting an existing identity raises
`CustomerAlreadyExistsError`; loading, adjusting, or deleting an absent account raises
`CustomerNotFoundError`. An adapter must enforce insertion atomically rather than implement a
check-then-insert race.

Order creation's inventory and payment ports include their matching compensation operations.
`ExportOrdersMailer.send_export_ready()` receives the returned download URL and the same optional
idempotency key as storage. Order confirmation has its own background-use-case mail port rather
than being an unused dependency of `CreateOrderHandler`.

## Transactions and audit evidence

`shop.ports.unit_of_work.UnitOfWork` is the explicit asynchronous transaction context used by
writing handlers. The application chooses the smallest block that must commit atomically.

`shop.ports.audit` defines the domain-event journal and its ordered reader. The journal accepts a
complete typed domain event and derives durable metadata. Database gateway protocols do not inherit
the journal port: handlers receive the two responsibilities separately even when one adapter
implements both on one transaction-bound connection.

## Integration messaging

The messaging modules have separate responsibilities:

- `integration.py` validates the versioned `IntegrationMessage` envelope and its exact JSON codec;
- `outbox.py` persists messages with trace context and leases committed work to a relay;
- `broker.py` publishes and consumes locked broker deliveries;
- `inbox.py` claims message identities and records completed processing.

The relay and consumer use leases because publication and processing can outlive one process. Lease
ownership, renewal, settlement, retries, and deduplication are infrastructure concerns; they do not
appear in business entities or mediator requests.

The delivery guarantee is at least once. Broker settlement prevents unnecessary retries, the inbox
prevents completed messages from being dispatched again, and effect-specific idempotency keys
protect mail and storage operations.

## Implementing a port

An adapter imports the protocols it implements and may implement several when one infrastructure
component naturally supplies them. It should not expose its client, session, cursor, SDK message,
or configuration through the protocol.

Ports do not hold credentials, create SDK clients, select provider lifetimes, or choose an
implementation. Those decisions belong to the adapter and `shop-bindings` composition root.

## Testing

Application unit tests call handlers directly with autospecced ports. They verify exact calls,
transaction boundaries, ordering, rollback, compensation, journal facts, outbox messages, and
idempotency keys without a mediator. Mediator integration tests then check the assembled application
graph. Concrete adapter tests cover transaction, concurrency, delivery, and storage behaviour; real
PostgreSQL and broker semantics use opt-in Testcontainers tests.

See the [flagship example guide](../../README.md), the
[background-processing guide](../../docs/background-processing.md), and the
[audit-journal guide](../../docs/audit-journal.md).
