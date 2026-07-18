"""Azure Service Bus integration-message adapter."""

from types import TracebackType
from typing import Any, Self, cast
from uuid import UUID

from azure.identity.aio import DefaultAzureCredential
from azure.servicebus import ServiceBusMessage
from azure.servicebus.aio import ServiceBusClient, ServiceBusReceiver
from shop.ports.broker import MessageConsumer, MessageDelivery, MessagePublisher
from shop.ports.integration import IntegrationMessage, deserialize_message, serialize_message
from shop.ports.outbox import OutboxMessage


class _ServiceBusDelivery(MessageDelivery):
    def __init__(self, receiver: ServiceBusReceiver, received: Any) -> None:
        self._receiver = receiver
        self._received = received

    @property
    def message(self) -> IntegrationMessage:
        body = b"".join(bytes(section) for section in self._received.body).decode()
        return deserialize_message(body)

    @property
    def trace_context(self) -> dict[str, str]:
        return {
            str(key): str(value)
            for key, value in (self._received.application_properties or {}).items()
        }

    @property
    def delivery_count(self) -> int:
        return int(self._received.delivery_count)

    async def complete(self) -> None:
        await self._receiver.complete_message(self._received)
        await self._receiver.close()

    async def abandon(self) -> None:
        await self._receiver.abandon_message(self._received)
        await self._receiver.close()

    async def renew(self) -> None:
        await self._receiver.renew_message_lock(self._received)


class AzureServiceBusMessageBroker(MessagePublisher, MessageConsumer):
    """Publish and consume envelopes through one Service Bus queue."""

    def __init__(
        self,
        queue_name: str,
        connection_string: str | None = None,
        fully_qualified_namespace: str | None = None,
        wait_seconds: int = 20,
    ) -> None:
        self._queue_name = queue_name
        self._wait_seconds = wait_seconds
        self._credential: DefaultAzureCredential | None = None
        if connection_string is not None:
            self._client = ServiceBusClient.from_connection_string(connection_string)
        elif fully_qualified_namespace is not None:
            self._credential = DefaultAzureCredential()
            self._client = ServiceBusClient(fully_qualified_namespace, self._credential)
        else:
            raise ValueError("connection_string or fully_qualified_namespace is required")

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.close()

    async def publish(self, outbox: OutboxMessage) -> None:
        message = outbox.message
        properties = cast(
            "dict[str | bytes, int | float | bytes | bool | str | UUID]",
            outbox.trace_context,
        )
        async with self._client.get_queue_sender(self._queue_name) as sender:
            await sender.send_messages(
                ServiceBusMessage(
                    serialize_message(message),
                    message_id=message.message_id,
                    application_properties=properties,
                )
            )

    async def receive(self) -> MessageDelivery | None:
        receiver = self._client.get_queue_receiver(
            self._queue_name, max_wait_time=self._wait_seconds
        )
        await receiver.__aenter__()
        messages = await receiver.receive_messages(max_message_count=1)
        if not messages:
            await receiver.close()
            return None
        return _ServiceBusDelivery(receiver, messages[0])

    async def close(self) -> None:
        """Close the Service Bus client and any managed-identity credential."""
        await self._client.close()
        if self._credential is not None:
            await self._credential.close()
