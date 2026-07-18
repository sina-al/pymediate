"""Narrow ports for the monthly-statement use case."""

from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable

from shop.domain.entities.orders import Order
from shop.domain.entities.statements import MonthlyStatement


@runtime_checkable
class CreateMonthlyStatementDbGateway(Protocol):
    """Stream period orders and persist their resulting statement."""

    def stream_orders_for_month(
        self, customer_id: int, year: int, month: int
    ) -> AsyncIterator[Order]: ...
    async def next_statement_identity(self) -> int: ...
    async def insert_statement(self, statement: MonthlyStatement) -> None: ...


@runtime_checkable
class StatementExchangeRates(Protocol):
    """Convert the shop's GBP minor units into a requested currency."""

    async def convert_from_gbp(self, amount_pence: int, currency: str) -> int: ...


@runtime_checkable
class MonthlyStatementRenderer(Protocol):
    """Render statement content independently from object storage."""

    async def render_statement(
        self,
        customer_id: int,
        year: int,
        month: int,
        currency: str,
        order_count: int,
        total_minor: int,
    ) -> bytes: ...


@runtime_checkable
class MonthlyStatementStorage(Protocol):
    """Persist a statement document and return its location."""

    async def write_statement(
        self, customer_id: int, year: int, month: int, content: bytes
    ) -> str: ...
