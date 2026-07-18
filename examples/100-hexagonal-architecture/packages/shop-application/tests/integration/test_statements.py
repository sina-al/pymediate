"""Exercise monthly-statement selection and calculation through mediator."""

from datetime import date

from shop.application.statements.create_monthly_statement import (
    CreateMonthlyStatementRequest,
)
from shop.domain.entities.orders import OrderLine
from shop.domain.events.base import AggregateType

from .support import ApplicationHarness


async def test_statement_selects_period_subtracts_refunds_and_ignores_cancellations(
    application: ApplicationHarness,
) -> None:
    # Arrange
    july = await application.seed_order(1, 7, (OrderLine("book", 2, 1_500),), date(2026, 7, 2))
    refunded = july.refund(1_000)
    await application.database.replace_order(refunded)
    cancelled = (await application.seed_order(2, 7, placed_on=date(2026, 7, 3))).cancel()
    await application.database.replace_order(cancelled)
    await application.seed_order(3, 7, placed_on=date(2026, 6, 30))
    await application.seed_order(4, 8, placed_on=date(2026, 7, 4))

    # Act
    statement = await application.mediator.send(CreateMonthlyStatementRequest(7, 2026, 7, "EUR"))

    # Assert
    assert statement.order_count == 1
    assert statement.total_minor == 2_340
    assert statement.document_url == "memory://statements/7/2026-07.pdf"
    statements = await application.database.statements()
    assert statements[0].statement_id == statement.statement_id
    assert statements[0].total_minor == statement.total_minor
    events = await application.events(AggregateType.STATEMENT, statement.statement_id)
    assert len(events) == 1
    assert events[0].event_type == "statements.monthly-statement-created"


async def test_empty_statement_is_still_rendered_and_persisted(
    application: ApplicationHarness,
) -> None:
    # Arrange
    request = CreateMonthlyStatementRequest(7, 2026, 7, "GBP")

    # Act
    statement = await application.mediator.send(request)

    # Assert
    assert statement.order_count == 0
    assert statement.total_minor == 0
    assert application.storage.documents["statements/7/2026-07.pdf"].startswith(b"%PDF-")
