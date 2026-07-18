"""Amazon SQS integration-message adapter."""

import asyncio
from types import TracebackType
from typing import Any, Self

import boto3

from shop.ports.broker import MessageConsumer, MessageDelivery, MessagePublisher
from shop.ports.integration import IntegrationMessage, deserialize_message, serialize_message
from shop.ports.outbox import OutboxMessage


class _SqsDelivery(MessageDelivery):
    def __init__(
        self,
        adapter: "SqsMessageBroker",
        body: str,
        receipt_handle: str,
        delivery_count: int,
        trace_context: dict[str, str],
    ) -> None:
        self._adapter = adapter
        self._body = body
        self._receipt_handle = receipt_handle
        self._delivery_count = delivery_count
        self._trace_context = trace_context

    @property
    def message(self) -> IntegrationMessage:
        return deserialize_message(self._body)

    @property
    def trace_context(self) -> dict[str, str]:
        return self._trace_context

    @property
    def delivery_count(self) -> int:
        return self._delivery_count

    async def complete(self) -> None:
        await self._adapter._delete(self._receipt_handle)

    async def abandon(self) -> None:
        await self._adapter._change_visibility(self._receipt_handle, 0)

    async def renew(self) -> None:
        await self._adapter._change_visibility(
            self._receipt_handle, self._adapter.visibility_seconds
        )


class SqsMessageBroker(MessagePublisher, MessageConsumer):
    """Publish and consume envelopes through one SQS standard queue."""

    def __init__(
        self,
        queue_url: str,
        region_name: str | None = None,
        endpoint_url: str | None = None,
        visibility_seconds: int = 120,
        wait_seconds: int = 20,
    ) -> None:
        self._queue_url = queue_url
        self.visibility_seconds = visibility_seconds
        self._wait_seconds = wait_seconds
        self._client: Any = boto3.client("sqs", region_name=region_name, endpoint_url=endpoint_url)

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await asyncio.to_thread(self._client.close)

    async def publish(self, outbox: OutboxMessage) -> None:
        message = outbox.message
        await asyncio.to_thread(
            self._client.send_message,
            QueueUrl=self._queue_url,
            MessageBody=serialize_message(message),
            MessageAttributes={
                key: {"DataType": "String", "StringValue": value}
                for key, value in outbox.trace_context.items()
            },
        )

    async def receive(self) -> MessageDelivery | None:
        response = await asyncio.to_thread(
            self._client.receive_message,
            QueueUrl=self._queue_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=self._wait_seconds,
            VisibilityTimeout=self.visibility_seconds,
            AttributeNames=["ApproximateReceiveCount"],
            MessageAttributeNames=["All"],
        )
        messages = response.get("Messages", [])
        if not messages:
            return None
        message = messages[0]
        return _SqsDelivery(
            self,
            str(message["Body"]),
            str(message["ReceiptHandle"]),
            int(message.get("Attributes", {}).get("ApproximateReceiveCount", "1")),
            {
                str(key): str(value["StringValue"])
                for key, value in message.get("MessageAttributes", {}).items()
            },
        )

    async def _delete(self, receipt_handle: str) -> None:
        await asyncio.to_thread(
            self._client.delete_message,
            QueueUrl=self._queue_url,
            ReceiptHandle=receipt_handle,
        )

    async def _change_visibility(self, receipt_handle: str, seconds: int) -> None:
        await asyncio.to_thread(
            self._client.change_message_visibility,
            QueueUrl=self._queue_url,
            ReceiptHandle=receipt_handle,
            VisibilityTimeout=seconds,
        )
