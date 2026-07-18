"""Exercise customer-account requests and cross-context policies via mediator."""

import pytest

from shop.application.customers.adjust_store_credit import AdjustStoreCreditRequest
from shop.application.customers.close_customer_account import CloseCustomerAccountRequest
from shop.application.customers.open_customer_account import OpenCustomerAccountRequest
from shop.application.orders.cancel_order import CancelOrderRequest
from shop.application.orders.refund_order import RefundOrderRequest
from shop.domain.errors.customers import (
    CustomerAlreadyExistsError,
    CustomerHasOpenOrdersError,
    CustomerNotFoundError,
    InvalidStoreCreditError,
)
from shop.domain.events.base import AggregateType

from .support import ApplicationHarness


async def test_customer_account_is_opened_through_the_mediator(
    application: ApplicationHarness,
) -> None:
    # Arrange
    customer_id = 7

    # Act
    result = await application.mediator.send(OpenCustomerAccountRequest(customer_id))

    # Assert
    assert result.customer_id == 7
    assert result.store_credit_pence == 0
    assert (await application.database.get_customer(7)).store_credit_pence == 0
    events = await application.events(AggregateType.CUSTOMER, 7)
    assert [event.event_type for event in events] == ["customers.account-opened"]


async def test_duplicate_customer_account_is_rejected_without_an_extra_event(
    application: ApplicationHarness,
) -> None:
    # Arrange
    await application.mediator.send(OpenCustomerAccountRequest(7))

    # Act
    with pytest.raises(CustomerAlreadyExistsError):
        await application.mediator.send(OpenCustomerAccountRequest(7))

    # Assert
    events = await application.events(AggregateType.CUSTOMER, 7)
    assert [event.event_type for event in events] == ["customers.account-opened"]


async def test_store_credit_is_adjusted_through_the_mediator(
    application: ApplicationHarness,
) -> None:
    # Arrange
    await application.mediator.send(OpenCustomerAccountRequest(7))

    # Act
    first = await application.mediator.send(AdjustStoreCreditRequest(7, 500))
    second = await application.mediator.send(AdjustStoreCreditRequest(7, 250))

    # Assert
    assert first.store_credit_pence == 500
    assert second.store_credit_pence == 750
    assert (await application.database.get_customer(7)).store_credit_pence == 750
    events = await application.events(AggregateType.CUSTOMER, 7)
    assert [event.payload.get("store_credit_pence") for event in events] == [None, 500, 750]


async def test_missing_customer_cannot_receive_store_credit(
    application: ApplicationHarness,
) -> None:
    # Arrange
    customer_id = 7

    # Act
    with pytest.raises(CustomerNotFoundError):
        await application.mediator.send(AdjustStoreCreditRequest(customer_id, 500))

    # Assert
    assert await application.database.customers() == []
    assert await application.events(AggregateType.CUSTOMER, 7) == ()


async def test_invalid_store_credit_rolls_back_without_adjustment_event(
    application: ApplicationHarness,
) -> None:
    # Arrange
    await application.mediator.send(OpenCustomerAccountRequest(7))

    # Act
    with pytest.raises(InvalidStoreCreditError):
        await application.mediator.send(AdjustStoreCreditRequest(7, 0))

    # Assert
    assert (await application.database.get_customer(7)).store_credit_pence == 0
    events = await application.events(AggregateType.CUSTOMER, 7)
    assert [event.event_type for event in events] == ["customers.account-opened"]


async def test_customer_with_open_order_cannot_be_closed(
    application: ApplicationHarness,
) -> None:
    # Arrange
    await application.mediator.send(OpenCustomerAccountRequest(7))
    await application.mediator.send(AdjustStoreCreditRequest(7, 500))
    await application.seed_order()

    # Act
    with pytest.raises(CustomerHasOpenOrdersError):
        await application.mediator.send(CloseCustomerAccountRequest(7))

    # Assert
    assert (await application.database.get_customer(7)).store_credit_pence == 500
    events = await application.events(AggregateType.CUSTOMER, 7)
    assert [event.event_type for event in events] == [
        "customers.account-opened",
        "customers.store-credit-adjusted",
    ]


async def test_missing_customer_cannot_be_closed(
    application: ApplicationHarness,
) -> None:
    # Arrange
    customer_id = 7

    # Act
    with pytest.raises(CustomerNotFoundError):
        await application.mediator.send(CloseCustomerAccountRequest(customer_id))

    # Assert
    assert await application.events(AggregateType.CUSTOMER, 7) == ()


@pytest.mark.parametrize("terminal_operation", ["cancel", "refund"])
async def test_customer_can_close_account_after_orders_are_terminal(
    application: ApplicationHarness,
    terminal_operation: str,
) -> None:
    # Arrange
    await application.mediator.send(OpenCustomerAccountRequest(7))
    await application.seed_order()
    if terminal_operation == "cancel":
        await application.mediator.send(CancelOrderRequest(1))
    else:
        await application.mediator.send(RefundOrderRequest(1, 3_000))

    # Act
    await application.mediator.send(CloseCustomerAccountRequest(7))

    # Assert
    assert all(customer.customer_id != 7 for customer in await application.database.customers())
    events = await application.events(AggregateType.CUSTOMER, 7)
    assert events[-1].event_type == "customers.account-closed"
