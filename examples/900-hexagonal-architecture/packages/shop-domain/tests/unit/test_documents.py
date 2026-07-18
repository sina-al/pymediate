"""Test invoice and statement snapshots at their domain boundary."""

from collections.abc import Callable
from functools import partial

import pytest

from shop.domain.entities.invoices import Invoice
from shop.domain.entities.statements import MonthlyStatement, StatementCurrency, StatementPeriod
from shop.domain.errors import DomainError, InvalidIdentifierError
from shop.domain.errors.invoices import InvalidInvoiceSnapshotError
from shop.domain.errors.orders import InvalidPriceError
from shop.domain.errors.statements import (
    InvalidCurrencyError,
    InvalidStatementPeriodError,
    InvalidStatementSnapshotError,
)


def _capture[ErrorT: DomainError](
    error_type: type[ErrorT], operation: Callable[[], object]
) -> ErrorT:
    try:
        operation()
    except error_type as error:
        return error
    raise AssertionError(f"{error_type.__name__} was not raised")


def _statement(**changes: object) -> MonthlyStatement:
    values: dict[str, object] = {
        "statement_id": 1,
        "customer_id": 7,
        "year": 2026,
        "month": 7,
        "currency": "GBP",
        "order_count": 2,
        "total_minor": 3_000,
        "document_url": "memory://statement.pdf",
    }
    values.update(changes)
    return MonthlyStatement(**values)  # type: ignore[arg-type]


def test_valid_invoice_keeps_its_public_snapshot() -> None:
    # Arrange
    document_url = "memory://invoice.pdf"

    # Act
    invoice = Invoice(1, 2, 7, 3_000, document_url)

    # Assert
    assert invoice.document_url == document_url
    assert invoice.total_pence == 3_000


@pytest.mark.parametrize(
    ("invoice_id", "order_id", "customer_id", "kind"),
    [(0, 2, 7, "invoice_id"), (1, 0, 7, "order_id"), (1, 2, 0, "customer_id")],
)
def test_invoice_identifiers_are_positive(
    invoice_id: int, order_id: int, customer_id: int, kind: str
) -> None:
    # Arrange
    create = partial(Invoice, invoice_id, order_id, customer_id, 3_000, "memory://invoice.pdf")

    # Act
    caught = _capture(InvalidIdentifierError, create)

    # Assert
    assert caught.context == {"kind": kind, "value": 0}


def test_invoice_total_is_positive() -> None:
    # Arrange
    create = partial(Invoice, 1, 2, 7, 0, "memory://invoice.pdf")

    # Act
    caught = _capture(InvalidPriceError, create)

    # Assert
    assert caught.context == {"price_pence": 0}


def test_invoice_document_location_is_required() -> None:
    # Arrange
    create = partial(Invoice, 1, 2, 7, 3_000, "")

    # Act
    caught = _capture(InvalidInvoiceSnapshotError, create)

    # Assert
    assert caught.context == {"field": "document_url", "value": ""}


@pytest.mark.parametrize(("year", "month"), [(0, 1), (2026, 0), (2026, 13), (True, 1)])
def test_statement_period_is_a_valid_calendar_month(year: int, month: int) -> None:
    # Arrange
    create = partial(StatementPeriod, year, month)

    # Act
    caught = _capture(InvalidStatementPeriodError, create)

    # Assert
    assert caught.context == {"year": year, "month": month}


@pytest.mark.parametrize("code", ["gbp", "CAD", "EU", 7, [], None])
def test_statement_currency_is_an_explicitly_supported_code(code: object) -> None:
    # Arrange
    create = partial(StatementCurrency, code)  # type: ignore[arg-type]

    # Act
    caught = _capture(InvalidCurrencyError, create)

    # Assert
    assert caught.context["currency"] == code
    assert caught.context["supported_currencies"] == ("GBP", "EUR", "USD")


def test_valid_monthly_statement_keeps_its_summary() -> None:
    # Arrange
    expected_url = "memory://statement.pdf"

    # Act
    statement = _statement(document_url=expected_url)

    # Assert
    assert statement.order_count == 2
    assert statement.total_minor == 3_000
    assert statement.document_url == expected_url


@pytest.mark.parametrize(
    ("changes", "error_type"),
    [
        ({"statement_id": 0}, InvalidIdentifierError),
        ({"customer_id": 0}, InvalidIdentifierError),
        ({"month": 13}, InvalidStatementPeriodError),
        ({"currency": "CAD"}, InvalidCurrencyError),
        ({"order_count": -1}, InvalidStatementSnapshotError),
        ({"order_count": True}, InvalidStatementSnapshotError),
        ({"total_minor": -1}, InvalidStatementSnapshotError),
        ({"total_minor": True}, InvalidStatementSnapshotError),
        ({"document_url": ""}, InvalidStatementSnapshotError),
    ],
)
def test_monthly_statement_rejects_inconsistent_snapshots(
    changes: dict[str, object], error_type: type[DomainError]
) -> None:
    # Arrange
    create = partial(_statement, **changes)

    # Act
    caught = _capture(error_type, create)

    # Assert
    assert caught.code.startswith("invalid-")
