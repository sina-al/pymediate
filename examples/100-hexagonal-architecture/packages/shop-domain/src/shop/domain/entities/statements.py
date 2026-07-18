"""Customer-statement entities owned by the statements feature module."""

from dataclasses import dataclass

from shop.domain.errors import InvalidIdentifierError
from shop.domain.errors.statements import (
    InvalidCurrencyError,
    InvalidStatementPeriodError,
    InvalidStatementSnapshotError,
)


@dataclass(frozen=True)
class StatementPeriod:
    """A valid calendar month selected for statement generation."""

    year: int
    month: int

    def __post_init__(self) -> None:
        if (
            not isinstance(self.year, int)
            or isinstance(self.year, bool)
            or self.year < 1
            or not isinstance(self.month, int)
            or isinstance(self.month, bool)
            or not 1 <= self.month <= 12
        ):
            raise InvalidStatementPeriodError(self.year, self.month)


@dataclass(frozen=True)
class StatementCurrency:
    """A three-letter currency code used for statement totals."""

    code: str

    def __post_init__(self) -> None:
        if not isinstance(self.code, str) or self.code not in {"GBP", "EUR", "USD"}:
            raise InvalidCurrencyError(self.code)


@dataclass(frozen=True)
class MonthlyStatement:
    """A persisted monthly order summary in the customer's requested currency."""

    statement_id: int
    customer_id: int
    year: int
    month: int
    currency: str
    order_count: int
    total_minor: int
    document_url: str

    def __post_init__(self) -> None:
        for kind, value in (
            ("statement_id", self.statement_id),
            ("customer_id", self.customer_id),
        ):
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise InvalidIdentifierError(kind, value)
        StatementPeriod(self.year, self.month)
        StatementCurrency(self.currency)
        if (
            not isinstance(self.order_count, int)
            or isinstance(self.order_count, bool)
            or self.order_count < 0
        ):
            raise InvalidStatementSnapshotError("order_count", self.order_count)
        if (
            not isinstance(self.total_minor, int)
            or isinstance(self.total_minor, bool)
            or self.total_minor < 0
        ):
            raise InvalidStatementSnapshotError("total_minor", self.total_minor)
        if not isinstance(self.document_url, str) or not self.document_url.strip():
            raise InvalidStatementSnapshotError("document_url", self.document_url)
