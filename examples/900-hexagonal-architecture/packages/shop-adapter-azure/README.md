# Shop Azure adapter

`shop-adapter-azure` provides Azure Blob Storage and Azure Service Bus implementations of the same
contracts used by the local and AWS profiles. The Shop can move from S3 and SQS to these
services without modifying its application handlers.

The package depends on `shop-ports` and the Azure Python SDKs. It does not import the application,
bindings, FastAPI, CLI adapter, or worker implementation.

## Modules

### `shop.adapters.azure.storage`

`AzureBlobStorage` implements export, invoice, and statement storage. It receives rendered bytes or
streamed rows with use-case identifiers, chooses blob names, writes them to the configured
container, and returns a document location. Deployment configuration supplies the container name
and connection string; Blob clients and Azure exceptions remain inside this adapter.

The application does not know whether storage uses a blob container, S3 bucket, or process-local
dictionary.

### `shop.adapters.azure.queue`

`AzureServiceBusMessageBroker` publishes versioned integration messages and receives queue
deliveries in peek-lock mode. The delivery wrapper maps the worker's transport-neutral operations
to Service Bus completion, abandonment, and lock renewal.

The consumer completes a message only after the mediator request and inbox completion succeed. A
failure abandons the message for another delivery. Lock renewal supports handlers that run longer
than the initial broker lock.

## Retry and duplicate behavior

Service Bus delivery is at least once. The worker inbox identifies completed message IDs and
prevents simultaneous processing. External mail and storage operations receive the same message ID
as an idempotency key.

The emulator configuration sets `MaxDeliveryCount` to five. Service Bus moves a message to its
dead-letter queue after repeated abandoned or expired deliveries; the application does not maintain
a parallel retry counter.

## Configuration and lifecycle

`configuration/azure.yaml` reads:

- `SHOP_AZURE_BLOB_CONTAINER` and `SHOP_AZURE_STORAGE_CONNECTION_STRING`;
- `SHOP_SERVICE_BUS_QUEUE` and `SHOP_SERVICE_BUS_CONNECTION_STRING`.

Bindings create Blob Storage and Service Bus clients as resources and close them with the host.
The `azure` infrastructure extra installs this package with PostgreSQL and the ephemeral support
services.

The local Compose profile uses Azurite for blobs and the official Service Bus emulator. Their
connection values belong to deployment configuration, not to the application.

## Testing

Fast worker tests use the process-local broker. The opt-in Service Bus emulator test verifies
publication, lock renewal, delivery-count redelivery, the configured five-attempt move to the
dead-letter subqueue, and completion. A focused unit test covers Blob upload translation with a
recording SDK client without changing application tests.

See the [complete Shop guide](../../README.md) for the Azure deployment and the
[background-processing guide](../../docs/background-processing.md) for queue settlement and retry
semantics.
