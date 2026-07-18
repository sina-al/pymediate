"""Test refund orchestration by calling the handler directly."""

from datetime import date
from unittest.mock import call

import pytest

from shop.application.orders.refund_order import RefundOrderHandler, RefundOrderRequest
from shop.domain.entities.orders import Order, OrderLine, OrderStatus
from shop.domain.errors.orders import ExcessiveRefundError
from shop.domain.events.orders import OrderRefundedEvent
from shop.ports.audit import DomainEventJournal
from shop.ports.orders.refund_order import (
    RefundOrderDbGateway,
    RefundOrderMailer,
    RefundOrderPaymentGateway,
)

from ..support import autospec, autospec_unit


def placed_order() -> Order:
    return Order.place(1, 7, (OrderLine("book", 2, 1_500),), date(2026, 7, 13))


async def test_refund_persists_before_calling_external_effects() -> None:
    # Arrange
    unit = autospec_unit()
    database = autospec(RefundOrderDbGateway)
    payments = autospec(RefundOrderPaymentGateway)
    mailer = autospec(RefundOrderMailer)
    journal = autospec(DomainEventJournal)
    database.get_order.return_value = placed_order()
    handle = RefundOrderHandler(unit, database, journal, payments, mailer)

    # Act
    result = await handle(RefundOrderRequest(1, 1_000))

    # Assert
    assert result.order_id == 1
    assert result.refunded_pence == 1_000
    assert result.status == OrderStatus.PARTIALLY_REFUNDED.value
    persisted = database.replace_order.await_args.args[0]
    assert persisted.refunded_pence == 1_000
    database.get_order.assert_awaited_once_with(1)
    journal.append.assert_awaited_once_with(
        OrderRefundedEvent(1, 7, 1_000, 1_000, "partially-refunded")
    )
    payments.refund.assert_awaited_once_with(1, 1_000)
    mailer.send.assert_awaited_once_with("customer-7@example.com", "Order 1 refunded")
    assert unit.mock_calls[:2] == [call.__aenter__(), call.__aexit__(None, None, None)]


async def test_invalid_refund_does_not_persist_or_call_external_services() -> None:
    # Arrange
    unit = autospec_unit()
    database = autospec(RefundOrderDbGateway)
    payments = autospec(RefundOrderPaymentGateway)
    mailer = autospec(RefundOrderMailer)
    journal = autospec(DomainEventJournal)
    database.get_order.return_value = placed_order()
    handle = RefundOrderHandler(unit, database, journal, payments, mailer)

    # Act
    with pytest.raises(ExcessiveRefundError):
        await handle(RefundOrderRequest(1, 4_000))

    # Assert
    database.replace_order.assert_not_awaited()
    payments.refund.assert_not_awaited()
    mailer.send.assert_not_awaited()
    assert unit.__aexit__.await_args.args[0] is ExcessiveRefundError


async def test_payment_failure_leaves_committed_refund_and_skips_mail() -> None:
    # Arrange
    unit = autospec_unit()
    database = autospec(RefundOrderDbGateway)
    payments = autospec(RefundOrderPaymentGateway)
    payments.refund.side_effect = RuntimeError("payments unavailable")
    mailer = autospec(RefundOrderMailer)
    journal = autospec(DomainEventJournal)
    database.get_order.return_value = placed_order()
    handle = RefundOrderHandler(unit, database, journal, payments, mailer)

    # Act
    with pytest.raises(RuntimeError, match="payments unavailable"):
        await handle(RefundOrderRequest(1, 1_000))

    # Assert
    database.replace_order.assert_awaited_once()
    journal.append.assert_awaited_once()
    unit.__aexit__.assert_awaited_once_with(None, None, None)
    mailer.send.assert_not_awaited()


async def test_mail_failure_occurs_after_payment_refund() -> None:
    # Arrange
    unit = autospec_unit()
    database = autospec(RefundOrderDbGateway)
    payments = autospec(RefundOrderPaymentGateway)
    mailer = autospec(RefundOrderMailer)
    mailer.send.side_effect = RuntimeError("mail unavailable")
    journal = autospec(DomainEventJournal)
    database.get_order.return_value = placed_order()
    handle = RefundOrderHandler(unit, database, journal, payments, mailer)

    # Act
    with pytest.raises(RuntimeError, match="mail unavailable"):
        await handle(RefundOrderRequest(1, 1_000))

    # Assert
    database.replace_order.assert_awaited_once()
    payments.refund.assert_awaited_once_with(1, 1_000)
    mailer.send.assert_awaited_once_with("customer-7@example.com", "Order 1 refunded")
