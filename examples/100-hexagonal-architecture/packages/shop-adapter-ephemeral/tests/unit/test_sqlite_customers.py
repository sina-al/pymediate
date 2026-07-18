"""Verify SQLite enforces explicit customer-account existence."""

import pytest

from shop.adapters.ephemeral import SqliteDbGateway, SqliteUnitOfWork
from shop.domain.entities.customers import CustomerAccount
from shop.domain.errors.customers import CustomerAlreadyExistsError, CustomerNotFoundError


async def test_customer_updates_never_create_an_account_implicitly(
    database: SqliteDbGateway,
) -> None:
    # Arrange
    customer = CustomerAccount.open(7)

    # Act
    with pytest.raises(CustomerNotFoundError):
        missing_unit = SqliteUnitOfWork(database)
        async with missing_unit:
            await database.replace_customer(customer.add_store_credit(500))

    create_unit = SqliteUnitOfWork(database)
    async with create_unit:
        await database.insert_customer(customer)

    with pytest.raises(CustomerAlreadyExistsError):
        duplicate_unit = SqliteUnitOfWork(database)
        async with duplicate_unit:
            await database.insert_customer(customer)

    update_unit = SqliteUnitOfWork(database)
    async with update_unit:
        await database.replace_customer(customer.add_store_credit(500))
    persisted = await database.get_customer(7)

    # Assert
    assert persisted.store_credit_pence == 500


async def test_missing_customer_reads_and_deletes_are_explicit_failures(
    database: SqliteDbGateway,
) -> None:
    # Arrange
    customer_id = 7

    # Act
    with pytest.raises(CustomerNotFoundError):
        await database.get_customer(customer_id)
    with pytest.raises(CustomerNotFoundError):
        unit = SqliteUnitOfWork(database)
        async with unit:
            await database.delete_customer(customer_id)

    # Assert
    assert await database.customers() == []


async def test_customer_delete_removes_an_existing_account(database: SqliteDbGateway) -> None:
    # Arrange
    customer = CustomerAccount.open(7)
    create_unit = SqliteUnitOfWork(database)
    async with create_unit:
        await database.insert_customer(customer)

    # Act
    delete_unit = SqliteUnitOfWork(database)
    async with delete_unit:
        await database.delete_customer(customer.customer_id)
    with pytest.raises(CustomerNotFoundError):
        await database.get_customer(customer.customer_id)

    # Assert
    assert await database.customers() == []
