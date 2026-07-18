# Shop application

`shop-application` contains the Shop's use cases, mediator graph, shared application services, and
cross-cutting request behaviours. FastAPI routes, Typer commands, and the queue consumer all send
the request types defined here through PyMediate.

The package depends on `shop-domain`, `shop-ports`, PyMediate, Dependency Injector, OpenTelemetry's
API, and structlog. It does not import `shop-bindings`, FastAPI, Typer, a database driver, a broker
SDK, or a concrete infrastructure adapter.

## Layout

```text
shop.application
├── customers/
├── invoices/
├── orders/
├── statements/
├── behaviours/
├── services/
├── container.py
├── integration_contracts.py
├── mediator.py
└── outbox_messages.py
```

Each operation is a module such as `orders.create_order` or
`customers.open_customer_account`. Its `*Request`, `*Response`, and `*Handler` types stay together.
Requests describe application intent. Responses explicitly select fields allowed to leave the
application; handlers do not return domain entities.

Feature `container.py` modules declare the dependencies and handlers owned by that feature. The
root `ApplicationContainer` supplies shared adapters and nests the feature containers. PyMediate's
Dependency Injector provider discovers handler providers in this nested graph, so hosts do not
maintain their own handler registries.

## Customer lifecycle

Customer accounts have an explicit lifecycle:

1. `OpenCustomerAccountRequest` inserts a zero-balance immutable account and journals
   `CustomerAccountOpenedEvent` in one transaction.
2. `AdjustStoreCreditRequest` loads an existing account, applies the domain transition, persists
   the replacement, and journals the adjustment.
3. `CloseCustomerAccountRequest` asks the orders capability whether work remains, then deletes an
   existing account and journals closure.

Missing accounts are not created as a side effect of a read or credit adjustment. Duplicate opens
and missing loads/deletes cross the application boundary as structured customer errors.

## Transaction and external-effect boundaries

Writing handlers own visible `async with self._unit` blocks. Database state, audit evidence, and
outbox messages written inside one block commit or roll back together. External calls are kept
outside those blocks where the workflow permits it.

Order creation demonstrates the foreground boundary explicitly:

1. load and validate catalogue data;
2. obtain an identity and construct the complete domain order;
3. reserve inventory;
4. charge payment;
5. commit the order, `OrderPlacedEvent`, confirmation message, and invoice message together.

Payment failure releases the reservation. A failure during the final local transaction refunds the
completed charge and releases inventory. Confirmation mail is not sent by this handler; it is
requested through the transactional outbox and performed by the worker.

This is an in-process compensation example, not a claim of atomicity across a database and remote
services. A process can stop between a remote effect and its compensation, and a timed-out payment
call can have an unknown result. A production workflow needing recovery across those windows should
persist workflow state and idempotency, such as the deferred Restate refund design under `todo/`.

Cancellation and refund also keep their remote payment, inventory, and mail operations visible.
Their tests document which local state has committed when an external call fails. The outbox-backed
background path carries the stronger crash-recovery example in this repository.

## Background contracts

`integration_contracts.py` defines application-owned wire facts such as
`OrderConfirmationRequestedV1`, `InvoiceRequestedV1`, and `OrderExportRequestedV1`. Their stable
`event_type`, integer schema version, and primitive payload form the compatibility contract.

`outbox_messages.py` creates a validated integration envelope and captures W3C trace context beside
it. It does not publish. A use case writes the envelope through its transaction-bound gateway; the
relay publishes committed rows, and the consumer translates `(event_type, schema_version)` into a
typed mediator request.

Domain events are journal facts; integration messages are process-boundary contracts; PyMediate
requests invoke application work. The example does not use `mediator.publish()` as a transaction
outbox and does not treat these three concepts as interchangeable.

Order export shows the completed background effect. The handler validates the format before
calling storage, streams the selected rows, receives a download URL, and passes that URL plus the
message idempotency key to the export-ready mail port.

## Behaviours and services

`shop.application.behaviours` contains request logging, tracing, and metrics behaviours. They are
registered once on the application mediator rather than repeated in each host. Logging records safe
request metadata, not arbitrary payloads.

OpenTelemetry's public API is used directly. `shop-bindings` configures the SDK and exporter for a
deployment; without an SDK the API is a no-op. The
[third-party abstractions guide](../../docs/third-party-abstractions.md) explains this dependency
choice.

`services.logger.StructlogLogger` is a small local implementation of the Shop logger port. A
concrete service does not require a separate adapter distribution until its dependencies,
lifecycle, or deployment selection need to vary.

## Testing

Tests under `tests/unit` instantiate every handler directly with autospecced protocols. They do not
use the mediator or dependency-injection container. The tests use separate Arrange, Act, and Assert
sections and verify responses, immutable transitions, exact events and messages, transaction exit,
external-effect ordering, compensation, and failure propagation.

Tests under `tests/integration` send requests through the real nested application container and
mediator with local adapters. They verify discovery, feature composition, dependency overrides, and
multi-request business journeys. Relay-to-consumer journeys belong to the worker and root acceptance
tests rather than this package.

See the [flagship example guide](../../README.md), the
[background-processing guide](../../docs/background-processing.md), and the
[audit-journal guide](../../docs/audit-journal.md).
