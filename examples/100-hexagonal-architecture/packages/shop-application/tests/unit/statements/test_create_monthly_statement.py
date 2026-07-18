"""Test monthly-statement orchestration by calling the handler directly."""

from collections.abc import AsyncIterator
from datetime import date

import pytest

from shop.application.statements.create_monthly_statement import (
    CreateMonthlyStatementHandler,
    CreateMonthlyStatementRequest,
)
from shop.domain.entities.orders import Order, OrderLine
from shop.domain.entities.statements import MonthlyStatement
from shop.domain.errors.statements import InvalidCurrencyError, InvalidStatementPeriodError
from shop.domain.events.statements import MonthlyStatementCreatedEvent
from shop.ports.audit import DomainEventJournal
from shop.ports.statements.create_monthly_statement import (
    CreateMonthlyStatementDbGateway,
    MonthlyStatementRenderer,
    MonthlyStatementStorage,
    StatementExchangeRates,
)

from ..support import autospec, autospec_unit


def stream(*orders: Order) -> AsyncIterator[Order]:
    async def values() -> AsyncIterator[Order]:
        for order in orders:
            yield order

    return values()


def placed(order_id: int, total: int = 1_500) -> Order:
    return Order.place(order_id, 7, (OrderLine("book", 1, total),), date(2026, 7, order_id))


async def test_statement_totals_active_orders_refunds_and_ignores_cancellations() -> None:
    # Arrange
    unit = autospec_unit()
    database = autospec(CreateMonthlyStatementDbGateway)
    rates = autospec(StatementExchangeRates)
    renderer = autospec(MonthlyStatementRenderer)
    storage = autospec(MonthlyStatementStorage)
    journal = autospec(DomainEventJournal)
    refunded = placed(2).refund(500)
    cancelled = placed(3).cancel()
    database.stream_orders_for_month.return_value = stream(placed(1), refunded, cancelled)
    database.next_statement_identity.return_value = 42
    rates.convert_from_gbp.return_value = 5_000
    renderer.render_statement.return_value = b"pdf"
    storage.write_statement.return_value = "s3://statements/7/2026-07.pdf"
    handle = CreateMonthlyStatementHandler(unit, database, rates, renderer, storage, journal)

    # Act
    result = await handle(CreateMonthlyStatementRequest(7, 2026, 7, "EUR"))

    # Assert
    expected = MonthlyStatement(42, 7, 2026, 7, "EUR", 2, 5_000, "s3://statements/7/2026-07.pdf")
    assert result.statement_id == 42
    assert result.order_count == 2
    assert result.total_minor == 5_000
    database.stream_orders_for_month.assert_called_once_with(7, 2026, 7)
    rates.convert_from_gbp.assert_awaited_once_with(2_500, "EUR")
    renderer.render_statement.assert_awaited_once_with(7, 2026, 7, "EUR", 2, 5_000)
    storage.write_statement.assert_awaited_once_with(7, 2026, 7, b"pdf")
    database.insert_statement.assert_awaited_once_with(expected)
    journal.append.assert_awaited_once_with(
        MonthlyStatementCreatedEvent(
            expected.statement_id,
            expected.customer_id,
            expected.year,
            expected.month,
            expected.currency,
            expected.order_count,
            expected.total_minor,
            expected.document_url,
        )
    )
    unit.__aexit__.assert_awaited_once_with(None, None, None)


async def test_empty_period_renders_and_persists_zero_statement() -> None:
    # Arrange
    unit = autospec_unit()
    database = autospec(CreateMonthlyStatementDbGateway)
    rates = autospec(StatementExchangeRates)
    renderer = autospec(MonthlyStatementRenderer)
    storage = autospec(MonthlyStatementStorage)
    journal = autospec(DomainEventJournal)
    database.stream_orders_for_month.return_value = stream()
    database.next_statement_identity.return_value = 1
    rates.convert_from_gbp.return_value = 0
    renderer.render_statement.return_value = b"empty"
    storage.write_statement.return_value = "memory://statement.pdf"
    handle = CreateMonthlyStatementHandler(unit, database, rates, renderer, storage, journal)

    # Act
    result = await handle(CreateMonthlyStatementRequest(7, 2026, 7))

    # Assert
    assert result.order_count == 0
    assert result.total_minor == 0
    rates.convert_from_gbp.assert_awaited_once_with(0, "GBP")


async def test_render_failure_prevents_storage_and_transaction() -> None:
    # Arrange
    unit = autospec_unit()
    database = autospec(CreateMonthlyStatementDbGateway)
    rates = autospec(StatementExchangeRates)
    renderer = autospec(MonthlyStatementRenderer)
    storage = autospec(MonthlyStatementStorage)
    journal = autospec(DomainEventJournal)
    database.stream_orders_for_month.return_value = stream(placed(1))
    rates.convert_from_gbp.return_value = 1_500
    renderer.render_statement.side_effect = RuntimeError("render failed")
    handle = CreateMonthlyStatementHandler(unit, database, rates, renderer, storage, journal)

    # Act
    with pytest.raises(RuntimeError, match="render failed"):
        await handle(CreateMonthlyStatementRequest(7, 2026, 7))

    # Assert
    storage.write_statement.assert_not_awaited()
    unit.__aenter__.assert_not_awaited()
    database.insert_statement.assert_not_awaited()


@pytest.mark.parametrize(
    ("statement_request", "error_type"),
    [
        (CreateMonthlyStatementRequest(7, 2026, 13), InvalidStatementPeriodError),
        (CreateMonthlyStatementRequest(7, 2026, 7, "CAD"), InvalidCurrencyError),
    ],
)
async def test_invalid_statement_input_fails_before_outbound_calls(
    statement_request: CreateMonthlyStatementRequest, error_type: type[Exception]
) -> None:
    # Arrange
    unit = autospec_unit()
    database = autospec(CreateMonthlyStatementDbGateway)
    rates = autospec(StatementExchangeRates)
    renderer = autospec(MonthlyStatementRenderer)
    storage = autospec(MonthlyStatementStorage)
    journal = autospec(DomainEventJournal)
    handle = CreateMonthlyStatementHandler(unit, database, rates, renderer, storage, journal)

    # Act
    with pytest.raises(error_type):
        await handle(statement_request)

    # Assert
    database.stream_orders_for_month.assert_not_called()
    rates.convert_from_gbp.assert_not_awaited()
    renderer.render_statement.assert_not_awaited()
    storage.write_statement.assert_not_awaited()
    unit.__aenter__.assert_not_awaited()
