# Shop domain

`shop-domain` contains the business state, transitions, facts, and expected failures used by the
example. The same objects are used when an operation starts in FastAPI, Typer, a queue consumer,
or a direct mediator call.

The package has no project or framework dependencies. It does not import PyMediate, Dependency
Injector, Pydantic, a database driver, or a cloud client library. Other Shop packages may depend on the
domain; the domain does not depend on them.

## Contents

The package is organised by kind of domain object rather than by transport or deployment:

```text
shop.domain
├── entities/
│   ├── customers.py
│   ├── invoices.py
│   ├── orders.py
│   └── statements.py
├── errors/
└── events/
```

`entities.orders` defines products, requested items, priced lines, order status, and the immutable
`Order`. Construction validates identifiers, SKUs, quantities, prices, line-derived totals,
business dates, refund totals, and status consistency. `Order.place()`, `refund()`, and `cancel()`
return coherent snapshots without persistence methods.

`entities.customers` defines `CustomerAccount`. `CustomerAccount.open()` creates a zero-balance
account, and `add_store_credit()` returns a new account. The entity rejects non-positive customer
identities, negative stored balances, and non-positive adjustments. Whether an account already
exists is determined atomically by persistence and expressed with a customer domain error.

`entities.invoices` and `entities.statements` define validated records for generated documents.
Statement periods and supported currencies (`GBP`, `EUR`, and `USD`) are domain values so direct
mediator calls receive the same validation as HTTP and command-line callers.

## Errors

`shop.domain.errors.DomainError` is the base for expected business failures. Each concrete error
provides:

- a stable machine-readable `code`;
- a short `title`;
- a safe human-readable `detail`;
- immutable structured `context`.

The package includes explicit customer existence errors, order state and snapshot errors, invalid
value errors, invoice lookup errors, and statement validation errors. A primary adapter may map
these values to Problem Details or terminal output, but no domain error selects an HTTP status or
terminal colour.

## Domain events

`shop.domain.events` contains versioned facts such as `OrderPlacedEvent`,
`CustomerAccountOpenedEvent`, and `InvoiceCreatedEvent`. An event owns its stable business name,
schema version, typed aggregate reference, and JavaScript Object Notation (JSON)-compatible
payload. Application handlers append
these events to the audit journal in the same transaction as the corresponding state change.

These are not PyMediate events and are not broker messages. The audit journal and an integration
queue have different consumers, identifiers, retention, delivery, and compatibility requirements.
The application defines integration contracts separately and performs an explicit translation when
background work is required.

## Dependency and ownership rule

Code belongs here when it can be applied without deciding:

- which adapter stores an object;
- which request invoked the operation;
- where a transaction begins;
- whether a message is published;
- which service renders, mails, or uploads a document.

Entities never call `save()`, acquire a database session, publish a message, or send mail. An
application handler loads state through a narrow port, invokes the domain operation, and coordinates
the required effects.

## Testing

Tests under `tests/unit` construct values and call operations directly. They cover valid immutable
transitions, invalid construction, reconstructed snapshot consistency, structured error context,
and stable event identity. They use no mediator, container, database, or mock.

See the [flagship example guide](../../README.md) for the complete request and background journeys.
The [audit-journal guide](../../docs/audit-journal.md) explains how these facts are retained without
making the application event sourced.
