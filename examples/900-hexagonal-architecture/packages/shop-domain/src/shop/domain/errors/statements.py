"""Business failures owned by the statements feature module."""

from shop.domain.errors import DomainError


class InvalidStatementPeriodError(DomainError, ValueError):
    code = "invalid-statement-period"
    title = "Invalid statement period"

    def __init__(self, year: int, month: int) -> None:
        super().__init__(
            "A statement period needs a positive year and a month from 1 to 12.",
            year=year,
            month=month,
        )


class InvalidCurrencyError(DomainError, ValueError):
    code = "invalid-currency"
    title = "Invalid statement currency"

    def __init__(self, currency: object) -> None:
        super().__init__(
            "Statement currency must be one of GBP, EUR, or USD.",
            currency=currency,
            supported_currencies=("GBP", "EUR", "USD"),
        )


class InvalidStatementSnapshotError(DomainError, ValueError):
    code = "invalid-statement-snapshot"
    title = "Invalid statement"

    def __init__(self, field: str, value: object) -> None:
        super().__init__(
            f"Statement field '{field}' is invalid.",
            field=field,
            value=value,
        )
