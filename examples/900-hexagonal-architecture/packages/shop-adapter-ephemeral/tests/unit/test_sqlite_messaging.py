"""Exercise SQLite lease ownership and task-owned transaction boundaries."""

import asyncio
from datetime import UTC, datetime

import pytest

from shop.adapters.ephemeral import SqliteDbGateway, SqliteUnitOfWork
from shop.domain.events.base import AggregateType
from shop.domain.events.orders import OrderPlacedEvent, OrderRefundedEvent
from shop.ports.inbox import InboxDisposition
from shop.ports.integration import IntegrationMessage
from shop.ports.outbox import OutboxMessage

MESSAGE_ID = "12345678-1234-5678-1234-567812345678"


def message() -> IntegrationMessage:
    return IntegrationMessage(
        MESSAGE_ID,
        "example.Event",
        1,
        datetime(2026, 7, 15, tzinfo=UTC),
        {},
    )


async def insert_message(database: SqliteDbGateway) -> None:
    unit = SqliteUnitOfWork(database)
    async with unit:
        await database.insert_outbox_message(OutboxMessage(message(), {}))


async def test_expired_outbox_claim_is_reclaimed_with_a_new_owner(
    database: SqliteDbGateway,
) -> None:
    # Arrange
    await insert_message(database)

    # Act
    stale = (await database.claim_outbox_messages(1, -1))[0]
    current = (await database.claim_outbox_messages(1, 120))[0]
    stale_marked = await database.mark_outbox_message_published(stale.message_id, stale.lease_token)
    stale_released = await database.release_outbox_message(stale.message_id, stale.lease_token)
    renewed = await database.renew_outbox_message(current.message_id, current.lease_token, 120)
    marked = await database.mark_outbox_message_published(current.message_id, current.lease_token)

    # Assert
    assert current.message == stale.message
    assert current.lease_token != stale.lease_token
    assert not stale_marked
    assert not stale_released
    assert renewed
    assert marked
    assert await database.claim_outbox_messages(1, 120) == ()


async def test_inbox_settlement_requires_the_current_lease_token(
    database: SqliteDbGateway,
) -> None:
    # Arrange
    message_id = MESSAGE_ID

    # Act
    first = await database.claim_inbox_message(message_id, 120)
    busy = await database.claim_inbox_message(message_id, 120)
    assert first.lease_token is not None
    released = await database.release_inbox_message(message_id, first.lease_token)
    current = await database.claim_inbox_message(message_id, 120)
    assert current.lease_token is not None
    stale_completion = await database.complete_inbox_message(message_id, first.lease_token)
    renewed = await database.renew_inbox_message(message_id, current.lease_token, 120)
    completed = await database.complete_inbox_message(message_id, current.lease_token)
    processed = await database.claim_inbox_message(message_id, 120)

    # Assert
    assert first.disposition is InboxDisposition.PROCESS
    assert busy.disposition is InboxDisposition.BUSY
    assert released
    assert current.disposition is InboxDisposition.PROCESS
    assert current.lease_token != first.lease_token
    assert not stale_completion
    assert renewed
    assert completed
    assert processed.disposition is InboxDisposition.PROCESSED


async def test_units_of_work_serialize_independent_transactions(
    database: SqliteDbGateway,
) -> None:
    # Arrange
    first_entered = asyncio.Event()
    release_first = asyncio.Event()
    second_entered = asyncio.Event()

    async def first() -> None:
        unit = SqliteUnitOfWork(database)
        async with unit:
            first_entered.set()
            await release_first.wait()

    async def second() -> None:
        await first_entered.wait()
        unit = SqliteUnitOfWork(database)
        async with unit:
            second_entered.set()

    # Act
    first_task = asyncio.create_task(first())
    second_task = asyncio.create_task(second())
    await first_entered.wait()
    await asyncio.sleep(0)
    blocked_before_release = not second_entered.is_set()
    release_first.set()
    await asyncio.gather(first_task, second_task)

    # Assert
    assert blocked_before_release
    assert second_entered.is_set()


async def test_unit_of_work_rejects_nesting_and_sequential_reuse(
    database: SqliteDbGateway,
) -> None:
    # Arrange
    outer = SqliteUnitOfWork(database)
    nested = SqliteUnitOfWork(database)

    # Act
    async with outer:
        with pytest.raises(RuntimeError, match="cannot be nested"):
            await nested.__aenter__()
    with pytest.raises(RuntimeError, match="cannot be reused"):
        await outer.__aenter__()

    # Assert
    assert await database.next_order_identity() == 1


async def test_transaction_access_cannot_escape_to_an_inherited_child_task(
    database: SqliteDbGateway,
) -> None:
    # Arrange
    unit = SqliteUnitOfWork(database)

    # Act
    async with unit:
        child = asyncio.create_task(database.orders())
        with pytest.raises(RuntimeError, match="child task"):
            await child

    # Assert
    assert await database.orders() == []


async def test_standalone_relay_access_waits_for_an_independent_transaction(
    database: SqliteDbGateway,
) -> None:
    # Arrange
    await insert_message(database)
    start_claim = asyncio.Event()

    async def claim_independently() -> int:
        await start_claim.wait()
        return len(await database.claim_outbox_messages(1, 120))

    claim_task = asyncio.create_task(claim_independently())
    unit = SqliteUnitOfWork(database)

    # Act
    async with unit:
        start_claim.set()
        await asyncio.sleep(0)
        blocked_inside_transaction = not claim_task.done()
    claimed = await claim_task

    # Assert
    assert blocked_inside_transaction
    assert claimed == 1


async def test_identity_allocation_is_unique_under_concurrency(
    database: SqliteDbGateway,
) -> None:
    # Arrange
    count = 20

    # Act
    identities = await asyncio.gather(*(database.next_order_identity() for _ in range(count)))

    # Assert
    assert sorted(identities) == list(range(1, count + 1))


async def test_domain_event_journal_is_ordered_and_rolls_back_atomically(
    database: SqliteDbGateway,
) -> None:
    # Arrange
    first = OrderPlacedEvent(42, 7, 1_500)
    second = OrderRefundedEvent(42, 7, 500, 500, "partially_refunded")

    # Act
    with pytest.raises(RuntimeError, match="rollback"):
        unit = SqliteUnitOfWork(database)
        async with unit:
            await database.append(first)
            raise RuntimeError("rollback")
    unit = SqliteUnitOfWork(database)
    async with unit:
        first_record = await database.append(first)
        second_record = await database.append(second)
    events = tuple(
        [event async for event in database.stream_domain_events(AggregateType.ORDER, "42")]
    )

    # Assert
    assert events == (first_record, second_record)
