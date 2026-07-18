"""Test account closure by calling the handler directly."""

from shop.application.customers.close_customer_account import (
    CloseCustomerAccountHandler,
    CloseCustomerAccountRequest,
)
from shop.domain.errors.customers import CustomerHasOpenOrdersError, CustomerNotFoundError
from shop.domain.events.customers import CustomerAccountClosedEvent
from shop.ports.audit import DomainEventJournal
from shop.ports.customers.close_customer_account import (
    CloseCustomerAccountDbGateway,
    CustomerOpenOrders,
)

from ..support import autospec, autospec_unit


async def test_customer_with_open_orders_is_rejected_before_transaction() -> None:
    # Arrange
    unit = autospec_unit()
    database = autospec(CloseCustomerAccountDbGateway)
    orders = autospec(CustomerOpenOrders)
    journal = autospec(DomainEventJournal)
    orders.has_open_orders.return_value = True
    handle = CloseCustomerAccountHandler(unit, database, orders, journal)
    caught: CustomerHasOpenOrdersError | None = None

    # Act
    try:
        await handle(CloseCustomerAccountRequest(7))
    except CustomerHasOpenOrdersError as error:
        caught = error

    # Assert
    assert caught is not None
    orders.has_open_orders.assert_awaited_once_with(7)
    unit.__aenter__.assert_not_awaited()
    database.delete_customer.assert_not_awaited()
    journal.append.assert_not_awaited()


async def test_customer_without_open_orders_is_deleted_in_transaction() -> None:
    # Arrange
    unit = autospec_unit()
    database = autospec(CloseCustomerAccountDbGateway)
    orders = autospec(CustomerOpenOrders)
    journal = autospec(DomainEventJournal)
    orders.has_open_orders.return_value = False
    handle = CloseCustomerAccountHandler(unit, database, orders, journal)

    # Act
    result = await handle(CloseCustomerAccountRequest(7))

    # Assert
    assert result.customer_id == 7
    database.delete_customer.assert_awaited_once_with(7)
    journal.append.assert_awaited_once_with(CustomerAccountClosedEvent(7))
    unit.__aexit__.assert_awaited_once_with(None, None, None)


async def test_missing_customer_rolls_back_without_a_closure_event() -> None:
    # Arrange
    unit = autospec_unit()
    database = autospec(CloseCustomerAccountDbGateway)
    database.delete_customer.side_effect = CustomerNotFoundError(7)
    orders = autospec(CustomerOpenOrders)
    orders.has_open_orders.return_value = False
    journal = autospec(DomainEventJournal)
    handle = CloseCustomerAccountHandler(unit, database, orders, journal)
    caught: CustomerNotFoundError | None = None

    # Act
    try:
        await handle(CloseCustomerAccountRequest(7))
    except CustomerNotFoundError as error:
        caught = error

    # Assert
    assert caught is not None
    journal.append.assert_not_awaited()
    assert unit.__aexit__.await_args.args[0] is CustomerNotFoundError
