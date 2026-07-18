"""Verify SQLite translations for the shop's business-owned records."""

import sqlite3
from datetime import date

import pytest

from shop.adapters.ephemeral import SqliteDbGateway, SqliteUnitOfWork
from shop.domain.entities.invoices import Invoice
from shop.domain.entities.orders import Order, OrderLine, OrderStatus
from shop.domain.entities.statements import MonthlyStatement
from shop.domain.errors.invoices import InvoiceNotFoundError
from shop.domain.errors.orders import OrderNotFoundError


def order(
    order_id: int,
    customer_id: int,
    placed_on: date,
    *,
    sku: str = "book",
    price_pence: int = 1_500,
) -> Order:
    """Build a valid persistence snapshot for an adapter test."""
    return Order.place(
        order_id,
        customer_id,
        (OrderLine(sku, 1, price_pence),),
        placed_on,
    )


async def persist_orders(database: SqliteDbGateway, *orders: Order) -> None:
    """Insert several records through one real SQLite transaction."""
    unit = SqliteUnitOfWork(database)
    async with unit:
        for placed in orders:
            await database.insert_order(placed)


async def test_orders_round_trip_and_stream_by_customer_and_month(
    database: SqliteDbGateway,
) -> None:
    # Arrange
    july = order(1, 7, date(2026, 7, 15))
    august = order(2, 7, date(2026, 8, 1), sku="mug", price_pence=900)
    another_customer = order(3, 8, date(2026, 7, 20))
    await persist_orders(database, july, august, another_customer)

    # Act
    found = await database.get_order(1)
    customer_orders = tuple([item async for item in database.stream_orders(7)])
    july_orders = tuple([item async for item in database.stream_orders_for_month(7, 2026, 7)])
    all_orders = await database.orders()

    # Assert
    assert found == july
    assert customer_orders == (july, august)
    assert july_orders == (july,)
    assert all_orders == [july, august, another_customer]


async def test_order_mutations_update_open_order_queries(
    database: SqliteDbGateway,
) -> None:
    # Arrange
    placed = order(1, 7, date(2026, 7, 15))
    await persist_orders(database, placed)

    # Act
    open_before = await database.has_open_orders(7)
    unit = SqliteUnitOfWork(database)
    async with unit:
        await database.replace_order(placed.cancel())
    open_after = await database.has_open_orders(7)
    persisted = await database.get_order(1)

    # Assert
    assert open_before
    assert not open_after
    assert persisted.status is OrderStatus.CANCELLED


async def test_missing_order_reads_raise_the_structured_domain_error(
    database: SqliteDbGateway,
) -> None:
    # Arrange
    missing_order_id = 404

    # Act
    with pytest.raises(OrderNotFoundError) as raised:
        await database.get_order(missing_order_id)

    # Assert
    assert raised.value.context == {"order_id": missing_order_id}


async def test_invoice_round_trip_enforces_one_invoice_per_order(
    database: SqliteDbGateway,
) -> None:
    # Arrange
    first = Invoice(1, 42, 7, 3_900, "memory://invoices/first.pdf")
    duplicate = Invoice(2, 42, 7, 3_900, "memory://invoices/duplicate.pdf")
    first_unit = SqliteUnitOfWork(database)
    async with first_unit:
        await database.insert_invoice(first)

    # Act
    with pytest.raises(sqlite3.IntegrityError):
        duplicate_unit = SqliteUnitOfWork(database)
        async with duplicate_unit:
            await database.insert_invoice(duplicate)
    persisted = await database.get_invoice_for_order(42)

    # Assert
    assert persisted == first
    assert await database.next_invoice_identity() == 1


async def test_missing_invoice_reads_raise_the_structured_domain_error(
    database: SqliteDbGateway,
) -> None:
    # Arrange
    missing_order_id = 404

    # Act
    with pytest.raises(InvoiceNotFoundError) as raised:
        await database.get_invoice_for_order(missing_order_id)

    # Assert
    assert raised.value.context == {"order_id": missing_order_id}


async def test_statement_snapshots_round_trip_in_identity_order(
    database: SqliteDbGateway,
) -> None:
    # Arrange
    later = MonthlyStatement(2, 8, 2026, 8, "EUR", 1, 1_800, "memory://later.pdf")
    earlier = MonthlyStatement(1, 7, 2026, 7, "GBP", 2, 3_900, "memory://earlier.pdf")

    # Act
    unit = SqliteUnitOfWork(database)
    async with unit:
        await database.insert_statement(later)
        await database.insert_statement(earlier)
    persisted = await database.statements()
    next_identity = await database.next_statement_identity()

    # Assert
    assert persisted == [earlier, later]
    assert next_identity == 1


async def test_business_writes_roll_back_together(database: SqliteDbGateway) -> None:
    # Arrange
    placed = order(1, 7, date(2026, 7, 15))
    invoice = Invoice(1, 1, 7, 1_500, "memory://invoices/1.pdf")
    statement = MonthlyStatement(1, 7, 2026, 7, "GBP", 1, 1_500, "memory://statement.pdf")

    # Act
    with pytest.raises(RuntimeError, match="abort transaction"):
        unit = SqliteUnitOfWork(database)
        async with unit:
            await database.insert_order(placed)
            await database.insert_invoice(invoice)
            await database.insert_statement(statement)
            raise RuntimeError("abort transaction")
    orders = await database.orders()
    statements = await database.statements()
    with pytest.raises(InvoiceNotFoundError):
        await database.get_invoice_for_order(1)

    # Assert
    assert orders == []
    assert statements == []
