"""Test order cancellation by calling the handler directly."""

from datetime import date

import pytest

from shop.application.orders.cancel_order import CancelOrderHandler, CancelOrderRequest
from shop.domain.entities.orders import Order, OrderItem, OrderLine, OrderStatus
from shop.domain.errors.orders import InvalidOrderStateError
from shop.domain.events.orders import OrderCancelledEvent
from shop.ports.audit import DomainEventJournal
from shop.ports.orders.cancel_order import (
    CancelOrderDbGateway,
    CancelOrderInventory,
    CancelOrderMailer,
    CancelOrderPaymentGateway,
)

from ..support import autospec, autospec_unit


def placed_order() -> Order:
    return Order.place(1, 7, (OrderLine("book", 2, 1_500),), date(2026, 7, 13))


async def test_cancel_persists_then_releases_voids_and_sends_mail() -> None:
    # Arrange
    unit = autospec_unit()
    database = autospec(CancelOrderDbGateway)
    inventory = autospec(CancelOrderInventory)
    payments = autospec(CancelOrderPaymentGateway)
    mailer = autospec(CancelOrderMailer)
    journal = autospec(DomainEventJournal)
    database.get_order.return_value = placed_order()
    handle = CancelOrderHandler(unit, database, journal, inventory, payments, mailer)

    # Act
    result = await handle(CancelOrderRequest(1))

    # Assert
    assert result.status == OrderStatus.CANCELLED.value
    persisted = database.replace_order.await_args.args[0]
    assert persisted.status is OrderStatus.CANCELLED
    journal.append.assert_awaited_once_with(OrderCancelledEvent(1, 7, 3_000))
    inventory.release.assert_awaited_once_with((OrderItem("book", 2),))
    payments.void.assert_awaited_once_with(1, 3_000)
    mailer.send.assert_awaited_once_with("customer-7@example.com", "Order 1 cancelled")
    unit.__aexit__.assert_awaited_once_with(None, None, None)


async def test_invalid_state_rolls_back_without_compensation() -> None:
    # Arrange
    unit = autospec_unit()
    database = autospec(CancelOrderDbGateway)
    inventory = autospec(CancelOrderInventory)
    payments = autospec(CancelOrderPaymentGateway)
    mailer = autospec(CancelOrderMailer)
    journal = autospec(DomainEventJournal)
    database.get_order.return_value = placed_order().cancel()
    handle = CancelOrderHandler(unit, database, journal, inventory, payments, mailer)

    # Act
    with pytest.raises(InvalidOrderStateError):
        await handle(CancelOrderRequest(1))

    # Assert
    database.replace_order.assert_not_awaited()
    inventory.release.assert_not_awaited()
    payments.void.assert_not_awaited()
    mailer.send.assert_not_awaited()
    assert unit.__aexit__.await_args.args[0] is InvalidOrderStateError


async def test_persistence_failure_prevents_external_compensation() -> None:
    # Arrange
    unit = autospec_unit()
    database = autospec(CancelOrderDbGateway)
    inventory = autospec(CancelOrderInventory)
    payments = autospec(CancelOrderPaymentGateway)
    mailer = autospec(CancelOrderMailer)
    journal = autospec(DomainEventJournal)
    database.get_order.return_value = placed_order()
    database.replace_order.side_effect = RuntimeError("write failed")
    handle = CancelOrderHandler(unit, database, journal, inventory, payments, mailer)

    # Act
    with pytest.raises(RuntimeError, match="write failed"):
        await handle(CancelOrderRequest(1))

    # Assert
    inventory.release.assert_not_awaited()
    payments.void.assert_not_awaited()
    mailer.send.assert_not_awaited()


async def test_inventory_failure_leaves_committed_cancellation_and_stops_later_effects() -> None:
    # Arrange
    unit = autospec_unit()
    database = autospec(CancelOrderDbGateway)
    inventory = autospec(CancelOrderInventory)
    inventory.release.side_effect = RuntimeError("inventory unavailable")
    payments = autospec(CancelOrderPaymentGateway)
    mailer = autospec(CancelOrderMailer)
    journal = autospec(DomainEventJournal)
    database.get_order.return_value = placed_order()
    handle = CancelOrderHandler(unit, database, journal, inventory, payments, mailer)

    # Act
    with pytest.raises(RuntimeError, match="inventory unavailable"):
        await handle(CancelOrderRequest(1))

    # Assert
    database.replace_order.assert_awaited_once()
    journal.append.assert_awaited_once()
    unit.__aexit__.assert_awaited_once_with(None, None, None)
    payments.void.assert_not_awaited()
    mailer.send.assert_not_awaited()


async def test_payment_failure_occurs_after_inventory_release_and_before_mail() -> None:
    # Arrange
    unit = autospec_unit()
    database = autospec(CancelOrderDbGateway)
    inventory = autospec(CancelOrderInventory)
    payments = autospec(CancelOrderPaymentGateway)
    payments.void.side_effect = RuntimeError("payments unavailable")
    mailer = autospec(CancelOrderMailer)
    journal = autospec(DomainEventJournal)
    database.get_order.return_value = placed_order()
    handle = CancelOrderHandler(unit, database, journal, inventory, payments, mailer)

    # Act
    with pytest.raises(RuntimeError, match="payments unavailable"):
        await handle(CancelOrderRequest(1))

    # Assert
    database.replace_order.assert_awaited_once()
    inventory.release.assert_awaited_once_with((OrderItem("book", 2),))
    mailer.send.assert_not_awaited()


async def test_mail_failure_occurs_after_cancellation_compensations() -> None:
    # Arrange
    unit = autospec_unit()
    database = autospec(CancelOrderDbGateway)
    inventory = autospec(CancelOrderInventory)
    payments = autospec(CancelOrderPaymentGateway)
    mailer = autospec(CancelOrderMailer)
    mailer.send.side_effect = RuntimeError("mail unavailable")
    journal = autospec(DomainEventJournal)
    database.get_order.return_value = placed_order()
    handle = CancelOrderHandler(unit, database, journal, inventory, payments, mailer)

    # Act
    with pytest.raises(RuntimeError, match="mail unavailable"):
        await handle(CancelOrderRequest(1))

    # Assert
    database.replace_order.assert_awaited_once()
    inventory.release.assert_awaited_once_with((OrderItem("book", 2),))
    payments.void.assert_awaited_once_with(1, 3_000)
