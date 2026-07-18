# Shop AWS adapter

`shop-adapter-aws` provides the Amazon Web Services (AWS) implementations needed by the Shop:
S3-compatible object storage and Simple Queue Service (SQS) message delivery. Selecting this
package changes infrastructure without changing
an application request or handler.

The package depends on `shop-ports` and the AWS Python software development kit (SDK). It does not
import the application, bindings, FastAPI, command-line adapter, or worker implementation.

## Modules

### `shop.adapters.aws.storage`

`S3Storage` implements export, invoice, and statement storage contracts. It receives rendered bytes
or streamed rows with use-case identifiers, chooses object keys, writes them to the configured
bucket, and returns their location. Deployment configuration supplies the bucket and endpoint; the
client and SDK details remain inside the adapter. The application does not know that an object is
stored in S3.

The endpoint is configurable so the same implementation can use AWS S3, MinIO, or another
S3-compatible service. The example Compose deployment uses MinIO because it provides a focused
local storage service without enabling unrelated LocalStack services.

### `shop.adapters.aws.queue`

`SqsMessageBroker` implements both message publication and competing consumption. It serializes the
versioned `IntegrationMessage`, sends it to a standard SQS queue, long-polls for deliveries, and
wraps a received message with the settlement operations required by the worker.

Completion deletes the SQS message. Abandonment returns it for redelivery. Lock renewal extends the
visibility timeout while a handler is running. Ordering is not part of the contract.

## Retry and duplicate behavior

The relay publishes before it marks an outbox row as published. A crash between those operations
can send the same `message_id` twice. The worker inbox and idempotency keys handle that expected
at-least-once behavior.

The Compose initialization creates a dead-letter queue and configures `maxReceiveCount: 5` on the
main queue. Repeatedly failing messages are moved by SQS rather than by application retry code.

## Configuration and lifecycle

`configuration/aws.yaml` supplies:

- `SHOP_S3_BUCKET` and optional `SHOP_S3_ENDPOINT` for storage;
- `SHOP_SQS_QUEUE_URL`, `SHOP_AWS_REGION`, and optional `SHOP_SQS_ENDPOINT` for messaging;
- AWS credentials through the normal SDK environment.

Bindings create the storage and broker providers as resources. Their SDK clients are closed when
the API or worker host exits.

The `aws` infrastructure extra installs this package with PostgreSQL and the ephemeral support
services. The API image receives storage but no worker package. Relay and consumer images receive
SQS support but no web framework.

## Testing

Application and worker logic use the process-local adapters for fast tests. The opt-in LocalStack
test verifies SQS publication, visibility renewal, receive-count redelivery, the configured
five-attempt move to a dead-letter queue, and completion from that queue. Storage is exercised against MinIO
without changing `S3Storage`.

See the [complete Shop guide](../../README.md) for the AWS deployment and the
[background-processing guide](../../docs/background-processing.md) for queue settlement and retry
semantics.
