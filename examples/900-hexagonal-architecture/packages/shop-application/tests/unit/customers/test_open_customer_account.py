"""Test explicit customer-account creation by calling the handler directly."""

from shop.application.customers.open_customer_account import (
    OpenCustomerAccountHandler,
    OpenCustomerAccountRequest,
)
from shop.domain.entities.customers import CustomerAccount
from shop.domain.errors.customers import CustomerAlreadyExistsError
from shop.domain.events.customers import CustomerAccountOpenedEvent
from shop.ports.audit import DomainEventJournal
from shop.ports.customers.open_customer_account import OpenCustomerAccountDbGateway

from ..support import autospec, autospec_unit


async def test_open_customer_persists_zero_balance_and_business_event() -> None:
    # Arrange
    unit = autospec_unit()
    database = autospec(OpenCustomerAccountDbGateway)
    journal = autospec(DomainEventJournal)
    handle = OpenCustomerAccountHandler(unit, database, journal)

    # Act
    result = await handle(OpenCustomerAccountRequest(7))

    # Assert
    assert result.customer_id == 7
    assert result.store_credit_pence == 0
    database.insert_customer.assert_awaited_once_with(CustomerAccount(7))
    journal.append.assert_awaited_once_with(CustomerAccountOpenedEvent(7))
    unit.__aexit__.assert_awaited_once_with(None, None, None)


async def test_duplicate_customer_rolls_back_without_recording_an_event() -> None:
    # Arrange
    unit = autospec_unit()
    database = autospec(OpenCustomerAccountDbGateway)
    database.insert_customer.side_effect = CustomerAlreadyExistsError(7)
    journal = autospec(DomainEventJournal)
    handle = OpenCustomerAccountHandler(unit, database, journal)
    caught: CustomerAlreadyExistsError | None = None

    # Act
    try:
        await handle(OpenCustomerAccountRequest(7))
    except CustomerAlreadyExistsError as error:
        caught = error

    # Assert
    assert caught is not None
    journal.append.assert_not_awaited()
    assert unit.__aexit__.await_args.args[0] is CustomerAlreadyExistsError
