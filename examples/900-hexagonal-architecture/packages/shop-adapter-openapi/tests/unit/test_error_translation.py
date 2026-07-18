"""Exercise the HTTP safety net independently from the application container."""

import logging

import httpx2
import pytest
from fastapi import FastAPI

from shop.domain.errors import DomainError, InvalidIdentifierError
from shop.domain.errors.customers import (
    CustomerAlreadyExistsError,
    CustomerHasOpenOrdersError,
    CustomerNotFoundError,
    InvalidStoreCreditError,
)
from shop.domain.errors.invoices import InvoiceNotFoundError
from shop.domain.errors.orders import (
    EmptyOrderError,
    ExcessiveRefundError,
    InvalidOrderStateError,
    InvalidPriceError,
    InvalidQuantityError,
    InvalidSkuError,
    OrderNotFoundError,
    ProductNotFoundError,
    UnsupportedExportFormatError,
)
from shop.domain.errors.statements import InvalidCurrencyError, InvalidStatementPeriodError
from shop.openapi.errors import register_domain_error_handlers


class NewlyIntroducedDomainError(DomainError):
    """Represent a domain failure whose HTTP policy was accidentally omitted."""

    code = "newly-introduced"
    title = "Newly introduced failure"


def test_each_known_domain_error_has_its_own_handler() -> None:
    # Arrange
    app = FastAPI()
    register_domain_error_handlers(app)
    error_types = {
        OrderNotFoundError,
        ProductNotFoundError,
        InvoiceNotFoundError,
        CustomerNotFoundError,
        CustomerAlreadyExistsError,
        EmptyOrderError,
        InvalidIdentifierError,
        InvalidQuantityError,
        InvalidSkuError,
        InvalidPriceError,
        ExcessiveRefundError,
        UnsupportedExportFormatError,
        InvalidOrderStateError,
        CustomerHasOpenOrdersError,
        InvalidStoreCreditError,
        InvalidStatementPeriodError,
        InvalidCurrencyError,
    }

    # Act
    handlers = [app.exception_handlers[error_type] for error_type in error_types]

    # Assert
    assert len(set(handlers)) == len(error_types)
    assert DomainError in app.exception_handlers


@pytest.mark.asyncio
async def test_unmapped_domain_error_is_logged_without_leaking_detail(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # Arrange
    app = FastAPI()
    register_domain_error_handlers(app)

    async def fail() -> None:
        raise NewlyIntroducedDomainError("sensitive internal domain detail", entity_id=42)

    app.add_api_route("/fail", fail)
    transport = httpx2.ASGITransport(app=app)

    # Act
    with caplog.at_level(logging.ERROR):
        async with httpx2.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/fail")

    # Assert
    assert response.status_code == 500
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json() == {
        "type": "/problems/unmapped-domain-error",
        "title": "Unexpected domain failure",
        "status": 500,
        "detail": "The request could not be completed.",
        "instance": "/fail",
        "code": "unmapped-domain-error",
        "context": {},
    }
    assert "NewlyIntroducedDomainError" in caplog.text
    assert "sensitive internal domain detail" in caplog.text
