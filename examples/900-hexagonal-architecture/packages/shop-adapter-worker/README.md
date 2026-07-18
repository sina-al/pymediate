# Shop worker adapter

`shop-adapter-worker` moves committed integration messages to a queue and turns queue deliveries
back into typed PyMediate requests. It lets confirmation mail, invoice generation, and order exports
run after the original HTTP or CLI request has completed.

This is an executable adapter. It depends inward on `shop-application`, `shop-ports`, and
`shop-bindings`. It does not depend directly on Amazon SQS or Azure Service
Bus; configured queue adapters implement the messaging ports.

## Two process roles

The `shop-worker` console script exposes `relay` and `consume` roles. In a durable profile, run
them as separate processes so each role can scale and restart independently. Both accept `--once`
for tests and operational checks.

The default profile cannot connect these roles across separate processes because its broker and
external effects are process-local. Use the root `poe demo` journey to run both roles together, or
select a durable profile before deploying them separately. The
[background-processing guide](../../docs/background-processing.md) explains the profile boundary.

### Relay

The relay leases a bounded batch of committed outbox messages. Every claim carries an opaque lease
token. A renewal task keeps all unpublished claims alive while the batch is processed. For each
message, the relay publishes the versioned envelope and conditionally marks the row as published
only after broker confirmation. Renewal, publication settlement, and release succeed only for the
current token, so an older relay cannot settle a lease that another process has reclaimed.

A crash after publication but before the database mark can create a duplicate. This is expected in
an at-least-once design and is handled by the consumer's inbox and idempotent effects.

### Consumer

The consumer receives a locked delivery, claims its `message_id` in the inbox, decodes the envelope,
and sends the resulting request through the same mediator used by HTTP and CLI.

If the inbox says `PROCESSED`, the delivery is completed without another dispatch. If it says
`BUSY`, the delivery is abandoned so the active consumer can finish. An expired processing lease
can be reclaimed. While a handler runs, a renewal task extends both the broker lock and the inbox
processing lease. Failure to renew either cancels dispatch and prevents acknowledgement.

Settlement is ordered: mediator dispatch, conditional inbox completion, then broker completion. A
decoding or handler failure before inbox completion conditionally releases the inbox claim and
abandons the delivery. If broker completion fails after the inbox is complete, the processed row is
retained. Redelivery is then completed without another dispatch. Cleanup errors are logged without
hiding the processing error. SQS or Service Bus retry and dead-letter configuration decides when a
repeatedly failing message stops returning.

## Modules

### `shop.worker.app`

Defines the CLI, selects relay or consumer, loads configuration, and owns wiring startup
and shutdown in one event loop.

### `shop.worker.container`

Defines two role-specific composition graphs. `RelayContainer` requires only the outbox source and
publisher. `ConsumerContainer` requires the queue, inbox, and application mediator. A relay process
therefore does not construct the application graph, while a consumer reuses its mediator.

### `shop.worker.relay`

Defines `OutboxRelay` and its lease, publish, confirm, and release sequence.

### `shop.worker.consumer`

Defines `MediatorMessageConsumer`, including inbox decisions, broker settlement, lock renewal, and
mediator dispatch.

### `shop.worker.registry`

Owns the explicit translation registry keyed by `(event_type, schema_version)`. Pydantic payload
models use strict validation and reject missing, extra, or coerced fields before a request is
constructed. `MessageRegistry` makes version support explicit rather than applying a latest-version
fallback. The current translations are:

- `shop.orders.order-confirmation-requested` version 1 to `SendOrderConfirmationRequest`;
- `shop.invoices.invoice-requested` version 1 to `CreateInvoiceRequest`;
- `shop.orders.order-export-requested` version 1 to `ExportOrdersRequest`.

The registry belongs to the worker because translating an integration contract into an application
request is an input concern. These are application-owned integration contracts, not serialized
domain event objects. Their names remain stable if a domain event class moves modules.

## Trace propagation

The consumer extracts the World Wide Web Consortium (W3C) trace carrier stored beside the
integration message, creates an
OpenTelemetry `CONSUMER` span, and then invokes the mediator. Application tracing therefore appears
below message processing in the same distributed trace. The carrier never enters the business
payload: SQS uses message attributes, Service Bus uses application properties, and the ephemeral
broker retains the `OutboxMessage` carrier separately.

## Queue independence

The default profile uses `EphemeralMessageBroker`, AWS uses
`SqsMessageBroker`, and Azure uses
`AzureServiceBusMessageBroker`. The relay and consumer code is identical in all three cases. Broker
differences are contained in their delivery implementations.

## Idempotency

Inbox deduplication prevents repeated mediator dispatch after successful processing. The message ID
also reaches external mail and storage ports as an idempotency key. Both layers matter: the inbox
protects the application request, while the idempotency key protects an effect if a failure occurs
after the effect but before inbox completion.

## Testing

Unit tests cover strict registry validation, an executable two-version registry example, stale lease
ownership, relay renewal, publication failures, inbox renewal, settlement ordering, and broker
completion failure. Complete journey tests run
`mediator → outbox → relay → ephemeral broker → consumer → mediator` for confirmation, invoice, and
export effects. The cloud packages contain opt-in adapter tests for publication, abandonment,
renewal, redelivery, and broker-managed dead-lettering at the configured threshold.

See the [background-processing guide](../../docs/background-processing.md) for the failure model,
sequence diagram, and contract boundaries, or the [complete Shop guide](../../README.md) for local
and cloud execution.
