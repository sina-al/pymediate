"""Test store-credit orchestration by calling the handler directly."""

from shop.application.customers.adjust_store_credit import (
    AdjustStoreCreditHandler,
    AdjustStoreCreditRequest,
)
from shop.domain.entities.customers import CustomerAccount
from shop.domain.errors.customers import CustomerNotFoundError, InvalidStoreCreditError
from shop.domain.events.customers import StoreCreditAdjustedEvent
from shop.ports.audit import DomainEventJournal
from shop.ports.customers.adjust_store_credit import AdjustStoreCreditDbGateway

from ..support import autospec, autospec_unit


async def test_adjust_credit_loads_applies_and_persists_immutable_account() -> None:
    # Arrange
    unit = autospec_unit()
    database = autospec(AdjustStoreCreditDbGateway)
    journal = autospec(DomainEventJournal)
    original = CustomerAccount(7, 500)
    database.get_customer.return_value = original
    handle = AdjustStoreCreditHandler(unit, database, journal)

    # Act
    result = await handle(AdjustStoreCreditRequest(7, 250))

    # Assert
    assert result.customer_id == 7
    assert result.store_credit_pence == 750
    assert original.store_credit_pence == 500
    database.get_customer.assert_awaited_once_with(7)
    database.replace_customer.assert_awaited_once_with(CustomerAccount(7, 750))
    journal.append.assert_awaited_once_with(StoreCreditAdjustedEvent(7, 250, 750))
    unit.__aenter__.assert_awaited_once_with()
    unit.__aexit__.assert_awaited_once_with(None, None, None)


async def test_invalid_credit_rolls_back_and_does_not_persist() -> None:
    # Arrange
    unit = autospec_unit()
    database = autospec(AdjustStoreCreditDbGateway)
    journal = autospec(DomainEventJournal)
    database.get_customer.return_value = CustomerAccount(7, 500)
    handle = AdjustStoreCreditHandler(unit, database, journal)
    caught: InvalidStoreCreditError | None = None

    # Act
    try:
        await handle(AdjustStoreCreditRequest(7, 0))
    except InvalidStoreCreditError as error:
        caught = error

    # Assert
    assert caught is not None
    database.replace_customer.assert_not_awaited()
    journal.append.assert_not_awaited()
    assert unit.__aexit__.await_args.args[0] is InvalidStoreCreditError


async def test_missing_customer_rolls_back_without_creating_an_account() -> None:
    # Arrange
    unit = autospec_unit()
    database = autospec(AdjustStoreCreditDbGateway)
    journal = autospec(DomainEventJournal)
    database.get_customer.side_effect = CustomerNotFoundError(7)
    handle = AdjustStoreCreditHandler(unit, database, journal)
    caught: CustomerNotFoundError | None = None

    # Act
    try:
        await handle(AdjustStoreCreditRequest(7, 250))
    except CustomerNotFoundError as error:
        caught = error

    # Assert
    assert caught is not None
    database.replace_customer.assert_not_awaited()
    journal.append.assert_not_awaited()
    assert unit.__aexit__.await_args.args[0] is CustomerNotFoundError
