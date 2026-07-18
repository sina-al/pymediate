"""Create a stored monthly statement from streamed order history."""

from dataclasses import dataclass

from pymediate import Request, RequestHandler

from shop.domain.entities.orders import OrderStatus
from shop.domain.entities.statements import MonthlyStatement, StatementCurrency, StatementPeriod
from shop.domain.events.statements import MonthlyStatementCreatedEvent
from shop.ports.audit import DomainEventJournal
from shop.ports.statements.create_monthly_statement import (
    CreateMonthlyStatementDbGateway,
    MonthlyStatementRenderer,
    MonthlyStatementStorage,
    StatementExchangeRates,
)
from shop.ports.unit_of_work import UnitOfWork


@dataclass(frozen=True)
class CreateMonthlyStatementResponse:
    """Public statement fields selected for application callers."""

    statement_id: int
    customer_id: int
    year: int
    month: int
    currency: str
    order_count: int
    total_minor: int
    document_url: str

    @classmethod
    def from_domain(cls, statement: MonthlyStatement) -> "CreateMonthlyStatementResponse":
        """Select the fields allowed to cross the application boundary."""
        return cls(
            statement.statement_id,
            statement.customer_id,
            statement.year,
            statement.month,
            statement.currency,
            statement.order_count,
            statement.total_minor,
            statement.document_url,
        )


@dataclass(frozen=True)
class CreateMonthlyStatementRequest(Request[CreateMonthlyStatementResponse]):
    """Request one customer's monthly statement in a chosen currency."""

    customer_id: int
    year: int
    month: int
    currency: str = "GBP"


class CreateMonthlyStatementHandler(RequestHandler[CreateMonthlyStatementRequest]):
    """Stream, convert, render, store, and persist one coherent statement."""

    def __init__(
        self,
        unit: UnitOfWork,
        database: CreateMonthlyStatementDbGateway,
        rates: StatementExchangeRates,
        renderer: MonthlyStatementRenderer,
        storage: MonthlyStatementStorage,
        journal: DomainEventJournal,
    ) -> None:
        self._unit = unit
        self._database = database
        self._rates = rates
        self._renderer = renderer
        self._storage = storage
        self._journal = journal

    async def __call__(
        self, request: CreateMonthlyStatementRequest
    ) -> CreateMonthlyStatementResponse:
        period = StatementPeriod(request.year, request.month)
        currency = StatementCurrency(request.currency)
        count = 0
        total_pence = 0
        async for order in self._database.stream_orders_for_month(
            request.customer_id, period.year, period.month
        ):
            if order.status is OrderStatus.CANCELLED:
                continue
            count += 1
            total_pence += order.total_pence - order.refunded_pence
        total_minor = await self._rates.convert_from_gbp(total_pence, currency.code)
        content = await self._renderer.render_statement(
            request.customer_id, period.year, period.month, currency.code, count, total_minor
        )
        url = await self._storage.write_statement(
            request.customer_id, period.year, period.month, content
        )
        async with self._unit:
            statement = MonthlyStatement(
                await self._database.next_statement_identity(),
                request.customer_id,
                period.year,
                period.month,
                currency.code,
                count,
                total_minor,
                url,
            )
            await self._database.insert_statement(statement)
            event = MonthlyStatementCreatedEvent(
                statement.statement_id,
                statement.customer_id,
                statement.year,
                statement.month,
                statement.currency,
                statement.order_count,
                statement.total_minor,
                statement.document_url,
            )
            await self._journal.append(event)
        return CreateMonthlyStatementResponse.from_domain(statement)
