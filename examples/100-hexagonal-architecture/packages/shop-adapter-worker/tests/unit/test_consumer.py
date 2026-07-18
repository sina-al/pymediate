"""Test inbox decisions and broker settlement around mediator dispatch."""

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from pymediate import Mediator, Request

from shop.ports.broker import MessageConsumer, MessageDelivery
from shop.ports.inbox import InboxClaim, MessageInbox
from shop.ports.integration import IntegrationMessage
from shop.ports.leases import LeaseToken
from shop.worker.consumer import InboxLeaseLostError, MediatorMessageConsumer

MESSAGE_ID = "12345678-1234-5678-1234-567812345678"
LEASE_TOKEN = LeaseToken(UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"))


@dataclass(frozen=True)
class ExampleRequest(Request[None]):
    message_id: str


@dataclass
class Delivery(MessageDelivery):
    _message: IntegrationMessage = field(
        default_factory=lambda: IntegrationMessage(
            MESSAGE_ID,
            "example.Event",
            1,
            datetime(2026, 7, 15, tzinfo=UTC),
            {},
        )
    )
    completed: int = 0
    abandoned: int = 0
    renewed: int = 0
    carrier: dict[str, str] = field(default_factory=dict)
    fail_complete: bool = False

    @property
    def message(self) -> IntegrationMessage:
        return self._message

    @property
    def trace_context(self) -> dict[str, str]:
        return self.carrier

    async def complete(self) -> None:
        self.completed += 1
        if self.fail_complete:
            raise RuntimeError("broker completion failed")

    async def abandon(self) -> None:
        self.abandoned += 1

    async def renew(self) -> None:
        self.renewed += 1


@dataclass
class Queue(MessageConsumer):
    delivery: Delivery | None

    async def receive(self) -> MessageDelivery | None:
        delivery, self.delivery = self.delivery, None
        return delivery


@dataclass
class Inbox(MessageInbox):
    result: InboxClaim = field(default_factory=lambda: InboxClaim.process(LEASE_TOKEN))
    fail_claim: bool = False
    renew_result: bool = True
    complete_result: bool = True
    completed: list[tuple[str, LeaseToken]] = field(default_factory=list)
    released: list[tuple[str, LeaseToken]] = field(default_factory=list)
    renewed: list[tuple[str, LeaseToken]] = field(default_factory=list)

    async def claim_inbox_message(self, message_id: str, lease_seconds: int) -> InboxClaim:
        if self.fail_claim:
            raise RuntimeError("inbox unavailable")
        return self.result

    async def renew_inbox_message(
        self, message_id: str, lease_token: LeaseToken, lease_seconds: int
    ) -> bool:
        self.renewed.append((message_id, lease_token))
        return self.renew_result

    async def complete_inbox_message(self, message_id: str, lease_token: LeaseToken) -> bool:
        self.completed.append((message_id, lease_token))
        return self.complete_result

    async def release_inbox_message(self, message_id: str, lease_token: LeaseToken) -> bool:
        self.released.append((message_id, lease_token))
        return True


@dataclass
class RecordingMediator:
    fail: bool = False
    delay: float = 0.005
    requests: list[Request[Any]] = field(default_factory=list)

    async def send(self, request: Request[Any]) -> Any:
        self.requests.append(request)
        await asyncio.sleep(self.delay)
        if self.fail:
            raise RuntimeError("handler failed")
        return None


def consumer(
    delivery: Delivery,
    inbox: Inbox,
    mediator: RecordingMediator,
    tracer: trace.Tracer | None = None,
) -> MediatorMessageConsumer:
    return MediatorMessageConsumer(
        Queue(delivery),
        inbox,
        cast("Mediator", mediator),
        lambda message: ExampleRequest(message.message_id),
        tracer or trace.NoOpTracerProvider().get_tracer("test"),
        renew_interval_seconds=0.001,
    )


async def test_success_completes_inbox_before_broker_with_both_leases_renewed() -> None:
    # Arrange
    delivery = Delivery()
    inbox = Inbox()
    mediator = RecordingMediator()

    # Act
    result = await consumer(delivery, inbox, mediator).run_once()

    # Assert
    assert result
    assert inbox.completed == [(MESSAGE_ID, LEASE_TOKEN)]
    assert inbox.renewed
    assert delivery.completed == 1
    assert delivery.renewed > 0


async def test_processed_duplicate_is_completed_without_dispatch() -> None:
    # Arrange
    delivery = Delivery()
    inbox = Inbox(InboxClaim.processed())
    mediator = RecordingMediator()

    # Act
    result = await consumer(delivery, inbox, mediator).run_once()

    # Assert
    assert result
    assert mediator.requests == []
    assert delivery.completed == 1


async def test_busy_duplicate_is_abandoned_without_dispatch() -> None:
    # Arrange
    delivery = Delivery()
    inbox = Inbox(InboxClaim.busy())
    mediator = RecordingMediator()

    # Act
    result = await consumer(delivery, inbox, mediator).run_once()

    # Assert
    assert result
    assert mediator.requests == []
    assert delivery.abandoned == 1


async def test_handler_failure_conditionally_releases_and_abandons() -> None:
    # Arrange
    delivery = Delivery()
    inbox = Inbox()
    mediator = RecordingMediator(fail=True)

    # Act
    with pytest.raises(RuntimeError, match="handler failed"):
        await consumer(delivery, inbox, mediator).run_once()

    # Assert
    assert inbox.released == [(MESSAGE_ID, LEASE_TOKEN)]
    assert delivery.abandoned == 1


async def test_inbox_claim_failure_abandons_the_broker_delivery() -> None:
    # Arrange
    delivery = Delivery()
    inbox = Inbox(fail_claim=True)
    mediator = RecordingMediator()

    # Act
    with pytest.raises(RuntimeError, match="inbox unavailable"):
        await consumer(delivery, inbox, mediator).run_once()

    # Assert
    assert mediator.requests == []
    assert delivery.abandoned == 1


async def test_lost_inbox_lease_cancels_processing_and_abandons() -> None:
    # Arrange
    delivery = Delivery()
    inbox = Inbox(renew_result=False)
    mediator = RecordingMediator(delay=0.1)

    # Act
    with pytest.raises(InboxLeaseLostError, match=MESSAGE_ID):
        await consumer(delivery, inbox, mediator).run_once()

    # Assert
    assert inbox.completed == []
    assert inbox.released == [(MESSAGE_ID, LEASE_TOKEN)]
    assert delivery.abandoned == 1


async def test_stale_inbox_completion_is_not_acknowledged() -> None:
    # Arrange
    delivery = Delivery()
    inbox = Inbox(complete_result=False)
    mediator = RecordingMediator()

    # Act
    with pytest.raises(InboxLeaseLostError, match=MESSAGE_ID):
        await consumer(delivery, inbox, mediator).run_once()

    # Assert
    assert inbox.released == [(MESSAGE_ID, LEASE_TOKEN)]
    assert delivery.abandoned == 1
    assert delivery.completed == 0


async def test_broker_completion_failure_keeps_the_processed_inbox_record() -> None:
    # Arrange
    delivery = Delivery(fail_complete=True)
    inbox = Inbox()
    mediator = RecordingMediator()

    # Act
    with pytest.raises(RuntimeError, match="broker completion failed"):
        await consumer(delivery, inbox, mediator).run_once()

    # Assert
    assert inbox.completed == [(MESSAGE_ID, LEASE_TOKEN)]
    assert inbox.released == []
    assert delivery.abandoned == 0


async def test_consumer_links_worker_and_mediator_work_to_persisted_trace() -> None:
    # Arrange
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("test.worker")
    trace_id = "0af7651916cd43dd8448eb211c80319c"
    delivery = Delivery(carrier={"traceparent": f"00-{trace_id}-b7ad6b7169203331-01"})
    inbox = Inbox()
    mediator = RecordingMediator()

    # Act
    await consumer(delivery, inbox, mediator, tracer).run_once()

    # Assert
    process = exporter.get_finished_spans()[0]
    assert process.context is not None
    assert f"{process.context.trace_id:032x}" == trace_id
    assert process.parent is not None
    assert f"{process.parent.span_id:016x}" == "b7ad6b7169203331"
    assert process.kind is trace.SpanKind.CONSUMER


async def test_empty_queue_returns_false() -> None:
    # Arrange
    subject = MediatorMessageConsumer(
        Queue(None),
        Inbox(),
        cast("Mediator", RecordingMediator()),
        lambda _: ExampleRequest("x"),
        trace.NoOpTracerProvider().get_tracer("test"),
    )

    # Act
    result = await subject.run_once()

    # Assert
    assert not result
