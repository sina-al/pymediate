"""Test outbox leasing, renewal, publication, and conditional settlement."""

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

import pytest

from shop.ports.broker import MessagePublisher
from shop.ports.integration import IntegrationMessage
from shop.ports.leases import LeaseToken
from shop.ports.outbox import OutboxClaim, OutboxMessage, OutboxRelaySource
from shop.worker.relay import OutboxLeaseLostError, OutboxRelay

MESSAGE_ID = "12345678-1234-5678-1234-567812345678"
LEASE_TOKEN = LeaseToken(UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"))


def claim() -> OutboxClaim:
    message = IntegrationMessage(
        MESSAGE_ID,
        "example.Event",
        1,
        datetime(2026, 7, 15, tzinfo=UTC),
        {},
    )
    return OutboxClaim(OutboxMessage(message, {}), LEASE_TOKEN)


@dataclass
class Outbox(OutboxRelaySource):
    claims: tuple[OutboxClaim, ...] = (claim(),)
    renew_result: bool = True
    mark_result: bool = True
    renewed: list[tuple[str, LeaseToken]] = field(default_factory=list)
    published: list[tuple[str, LeaseToken]] = field(default_factory=list)
    released: list[tuple[str, LeaseToken]] = field(default_factory=list)

    async def claim_outbox_messages(
        self, limit: int, lease_seconds: int
    ) -> tuple[OutboxClaim, ...]:
        return self.claims[:limit]

    async def renew_outbox_message(
        self, message_id: str, lease_token: LeaseToken, lease_seconds: int
    ) -> bool:
        self.renewed.append((message_id, lease_token))
        return self.renew_result

    async def mark_outbox_message_published(self, message_id: str, lease_token: LeaseToken) -> bool:
        self.published.append((message_id, lease_token))
        return self.mark_result

    async def release_outbox_message(self, message_id: str, lease_token: LeaseToken) -> bool:
        self.released.append((message_id, lease_token))
        return True


@dataclass
class Publisher(MessagePublisher):
    messages: list[OutboxMessage] = field(default_factory=list)
    delay: float = 0
    fail_after_publish: bool = False

    async def publish(self, outbox: OutboxMessage) -> None:
        self.messages.append(outbox)
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.fail_after_publish:
            raise RuntimeError("confirmation lost")


async def test_relay_marks_only_broker_confirmed_messages() -> None:
    # Arrange
    outbox = Outbox()
    publisher = Publisher()
    relay = OutboxRelay(outbox, publisher)

    # Act
    published = await relay.run_once()

    # Assert
    assert published == 1
    assert outbox.published == [(MESSAGE_ID, LEASE_TOKEN)]
    assert outbox.released == []


async def test_publish_confirmation_failure_releases_owned_lease() -> None:
    # Arrange
    outbox = Outbox()
    publisher = Publisher(fail_after_publish=True)
    relay = OutboxRelay(outbox, publisher)

    # Act
    with pytest.raises(RuntimeError, match="confirmation lost"):
        await relay.run_once()

    # Assert
    assert [message.message_id for message in publisher.messages] == [MESSAGE_ID]
    assert outbox.published == []
    assert outbox.released == [(MESSAGE_ID, LEASE_TOKEN)]


async def test_slow_publication_renews_the_claim_before_settlement() -> None:
    # Arrange
    outbox = Outbox()
    publisher = Publisher(delay=0.01)
    relay = OutboxRelay(outbox, publisher, renew_interval_seconds=0.001)

    # Act
    published = await relay.run_once()

    # Assert
    assert published == 1
    assert outbox.renewed
    assert outbox.published == [(MESSAGE_ID, LEASE_TOKEN)]


async def test_lost_lease_prevents_a_stale_relay_from_marking_published() -> None:
    # Arrange
    outbox = Outbox(mark_result=False)
    relay = OutboxRelay(outbox, Publisher())

    # Act
    with pytest.raises(OutboxLeaseLostError, match=MESSAGE_ID):
        await relay.run_once()

    # Assert
    assert outbox.published == [(MESSAGE_ID, LEASE_TOKEN)]
    assert outbox.released == [(MESSAGE_ID, LEASE_TOKEN)]


async def test_failed_renewal_prevents_settlement_after_slow_publication() -> None:
    # Arrange
    outbox = Outbox(renew_result=False)
    relay = OutboxRelay(
        outbox,
        Publisher(delay=0.01),
        renew_interval_seconds=0.001,
    )

    # Act
    with pytest.raises(OutboxLeaseLostError, match=MESSAGE_ID):
        await relay.run_once()

    # Assert
    assert outbox.renewed == [(MESSAGE_ID, LEASE_TOKEN)]
    assert outbox.published == []
    assert outbox.released == [(MESSAGE_ID, LEASE_TOKEN)]
