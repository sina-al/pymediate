"""Exercise the SQS adapter against LocalStack through Testcontainers."""

import json
import os
from datetime import UTC, datetime
from typing import Protocol, cast

import boto3
import pytest
from testcontainers.localstack import LocalStackContainer

from shop.adapters.aws import SqsMessageBroker
from shop.ports.integration import IntegrationMessage
from shop.ports.outbox import OutboxMessage


class CountedDelivery(Protocol):
    """Expose the SQS-specific delivery count asserted by this adapter test."""

    delivery_count: int


@pytest.mark.containers
async def test_sqs_renew_redeliver_and_move_poison_message_to_dlq(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    if os.environ.get("RUN_BROKER_TESTCONTAINERS") != "1":
        pytest.skip("set RUN_BROKER_TESTCONTAINERS=1 to run broker integrations")

    # Act
    with LocalStackContainer(image="localstack/localstack:4.0").with_services("sqs") as localstack:
        client = boto3.client(
            "sqs",
            endpoint_url=localstack.get_url(),
            region_name=localstack.region_name,
            aws_access_key_id="testcontainers-localstack",
            aws_secret_access_key="testcontainers-localstack",
        )
        dead_letter_url = client.create_queue(QueueName="shop-events-dlq")["QueueUrl"]
        dead_letter_arn = client.get_queue_attributes(
            QueueUrl=dead_letter_url,
            AttributeNames=["QueueArn"],
        )["Attributes"]["QueueArn"]
        queue_url = client.create_queue(
            QueueName="shop-events",
            Attributes={
                "RedrivePolicy": json.dumps(
                    {
                        "deadLetterTargetArn": dead_letter_arn,
                        "maxReceiveCount": "5",
                    }
                )
            },
        )["QueueUrl"]
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testcontainers-localstack")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testcontainers-localstack")
        message = IntegrationMessage(
            "12345678-1234-5678-1234-567812345678",
            "example.Event",
            1,
            datetime(2026, 7, 15, tzinfo=UTC),
            {},
        )

        async with (
            SqsMessageBroker(
                queue_url,
                region_name=localstack.region_name,
                endpoint_url=localstack.get_url(),
                wait_seconds=1,
            ) as adapter,
            SqsMessageBroker(
                dead_letter_url,
                region_name=localstack.region_name,
                endpoint_url=localstack.get_url(),
                wait_seconds=1,
            ) as dead_letters,
        ):
            await adapter.publish(OutboxMessage(message, {}))
            first = await adapter.receive()
            assert first is not None
            await first.renew()
            await first.abandon()

            delivery_counts: list[int] = []
            for _ in range(4):
                delivery = await adapter.receive()
                assert delivery is not None
                delivery_counts.append(cast("CountedDelivery", delivery).delivery_count)
                await delivery.abandon()

            source_after_threshold = await adapter.receive()
            dead_letter = await dead_letters.receive()
            assert dead_letter is not None
            dead_letter_message = dead_letter.message
            await dead_letter.complete()
            dead_letter_after_completion = await dead_letters.receive()

        # Assert
        assert first.message == message
        assert delivery_counts == [2, 3, 4, 5]
        assert source_after_threshold is None
        assert dead_letter_message == message
        assert dead_letter_after_completion is None
