"""Exercise PostgreSQL pool, row-lock, identity, and lease concurrency."""

import asyncio
import os
from datetime import UTC, date, datetime

import pytest
from testcontainers.postgres import PostgresContainer

from shop.adapters.postgres import PostgresDbGateway, PostgresUnitOfWork
from shop.domain.entities.customers import CustomerAccount
from shop.domain.entities.orders import Order, OrderLine, OrderStatus
from shop.ports.integration import IntegrationMessage
from shop.ports.outbox import OutboxClaim, OutboxMessage


@pytest.mark.containers
async def test_postgres_transactions_and_leases_are_safe_under_concurrency() -> None:
    # Arrange
    if os.environ.get("RUN_TESTCONTAINERS") != "1":
        pytest.skip("set RUN_TESTCONTAINERS=1 to run Docker integrations")
    postgres = PostgresContainer("postgres:17-alpine", driver=None)

    # Act
    with postgres:
        database = PostgresDbGateway(postgres.get_connection_url())
        await asyncio.gather(*(database.__aenter__() for _ in range(5)))
        order_id = await database.next_order_identity()
        order = Order.place(
            order_id,
            7,
            (OrderLine("book", 1, 1_500),),
            date(2026, 7, 15),
        )
        envelope = IntegrationMessage(
            "12345678-1234-5678-1234-567812345678",
            "example.Event",
            1,
            datetime(2026, 7, 15, tzinfo=UTC),
            {},
        )
        unit = PostgresUnitOfWork(database)
        async with unit:
            await database.insert_customer(CustomerAccount.open(7))
            await database.insert_order(order)
            await database.insert_outbox_message(OutboxMessage(envelope, {}))

        first_locked = asyncio.Event()
        release_first = asyncio.Event()
        second_locked = asyncio.Event()

        async def first_writer() -> None:
            first_unit = PostgresUnitOfWork(database)
            async with first_unit:
                await database.get_order(order_id)
                first_locked.set()
                await release_first.wait()

        async def second_writer() -> None:
            await first_locked.wait()
            second_unit = PostgresUnitOfWork(database)
            async with second_unit:
                await database.get_order(order_id)
                second_locked.set()

        first_task = asyncio.create_task(first_writer())
        second_task = asyncio.create_task(second_writer())
        await first_locked.wait()
        await asyncio.sleep(0.05)
        blocked_by_row_lock = not second_locked.is_set()
        release_first.set()
        await asyncio.gather(first_task, second_task)

        with pytest.raises(RuntimeError, match="rollback"):
            rollback = PostgresUnitOfWork(database)
            async with rollback:
                await database.replace_order(order.cancel())
                raise RuntimeError("rollback")
        after_rollback = await database.get_order(order_id)

        start_relay = asyncio.Event()

        async def claim_independently() -> OutboxClaim:
            await start_relay.wait()
            return (await database.claim_outbox_messages(1, -1))[0]

        claim_task = asyncio.create_task(claim_independently())
        business_unit = PostgresUnitOfWork(database)
        async with business_unit:
            await database.get_order(order_id)
            start_relay.set()
            stale = await asyncio.wait_for(claim_task, timeout=1)

        task_owned_unit = PostgresUnitOfWork(database)
        async with task_owned_unit:
            child = asyncio.create_task(database.get_order(order_id))
            with pytest.raises(RuntimeError, match="child task"):
                await child
        order_after_child_rejection = await database.get_order(order_id)

        identities = await asyncio.gather(*(database.next_order_identity() for _ in range(20)))
        current = (await database.claim_outbox_messages(1, 120))[0]
        stale_marked = await database.mark_outbox_message_published(
            stale.message_id, stale.lease_token
        )
        current_marked = await database.mark_outbox_message_published(
            current.message_id, current.lease_token
        )
        with pytest.raises(RuntimeError, match="cannot be reused"):
            await unit.__aenter__()
        await database.close()

    # Assert
    assert blocked_by_row_lock
    assert second_locked.is_set()
    assert after_rollback.status is OrderStatus.PLACED
    assert len(set(identities)) == 20
    assert current.lease_token != stale.lease_token
    assert not stale_marked
    assert current_marked
    assert order_after_child_rejection.order_id == order_id
