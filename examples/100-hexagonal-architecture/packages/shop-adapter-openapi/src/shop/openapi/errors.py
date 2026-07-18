"""Translate domain failures into RFC 9457 problem details at the HTTP edge."""

import logging
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

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
from shop.openapi import dto

logger = logging.getLogger(__name__)


DOMAIN_PROBLEM_RESPONSES: dict[int | str, dict[str, Any]] = {
    HTTPStatus.NOT_FOUND: {
        "description": "A requested shop resource does not exist.",
        "content": {
            "application/problem+json": {"schema": dto.ProblemDetailsResponse.model_json_schema()}
        },
    },
    HTTPStatus.CONFLICT: {
        "description": "The operation conflicts with current domain state.",
        "content": {
            "application/problem+json": {"schema": dto.ProblemDetailsResponse.model_json_schema()}
        },
    },
    HTTPStatus.UNPROCESSABLE_ENTITY: {
        "description": "The input is valid HTTP but violates a domain rule.",
        "content": {
            "application/problem+json": {"schema": dto.ProblemDetailsResponse.model_json_schema()}
        },
    },
}


def _problem_response(problem: dto.ProblemDetailsResponse) -> JSONResponse:
    return JSONResponse(
        status_code=problem.status,
        content=problem.model_dump(mode="json"),
        media_type="application/problem+json",
    )


def _domain_problem(
    request: Request,
    error: DomainError,
    status: HTTPStatus,
    log_level: int = logging.INFO,
) -> JSONResponse:
    """Render one explicitly mapped domain failure as problem details."""
    logger.log(
        log_level,
        "Domain error %s while handling %s: %s",
        error.code,
        request.url.path,
        error.detail,
    )
    return _problem_response(
        dto.ProblemDetailsResponse(
            type=f"/problems/{error.code}",
            title=error.title,
            status=status,
            detail=error.detail,
            instance=request.url.path,
            code=error.code,
            context=dict(error.context),
        )
    )


def register_domain_error_handlers(app: FastAPI) -> None:
    """Install explicit domain mappings plus a safe fallback for future errors."""

    @app.exception_handler(OrderNotFoundError)
    async def order_not_found(request: Request, error: OrderNotFoundError) -> JSONResponse:
        return _domain_problem(request, error, HTTPStatus.NOT_FOUND)

    @app.exception_handler(ProductNotFoundError)
    async def product_not_found(request: Request, error: ProductNotFoundError) -> JSONResponse:
        return _domain_problem(request, error, HTTPStatus.NOT_FOUND)

    @app.exception_handler(InvoiceNotFoundError)
    async def invoice_not_found(request: Request, error: InvoiceNotFoundError) -> JSONResponse:
        return _domain_problem(request, error, HTTPStatus.NOT_FOUND)

    @app.exception_handler(CustomerNotFoundError)
    async def customer_not_found(request: Request, error: CustomerNotFoundError) -> JSONResponse:
        return _domain_problem(request, error, HTTPStatus.NOT_FOUND)

    @app.exception_handler(CustomerAlreadyExistsError)
    async def customer_already_exists(
        request: Request, error: CustomerAlreadyExistsError
    ) -> JSONResponse:
        return _domain_problem(request, error, HTTPStatus.CONFLICT, logging.WARNING)

    @app.exception_handler(EmptyOrderError)
    async def empty_order(request: Request, error: EmptyOrderError) -> JSONResponse:
        return _domain_problem(request, error, HTTPStatus.UNPROCESSABLE_ENTITY)

    @app.exception_handler(InvalidQuantityError)
    async def invalid_quantity(request: Request, error: InvalidQuantityError) -> JSONResponse:
        return _domain_problem(request, error, HTTPStatus.UNPROCESSABLE_ENTITY)

    @app.exception_handler(InvalidIdentifierError)
    async def invalid_identifier(request: Request, error: InvalidIdentifierError) -> JSONResponse:
        return _domain_problem(request, error, HTTPStatus.UNPROCESSABLE_ENTITY)

    @app.exception_handler(InvalidSkuError)
    async def invalid_sku(request: Request, error: InvalidSkuError) -> JSONResponse:
        return _domain_problem(request, error, HTTPStatus.UNPROCESSABLE_ENTITY)

    @app.exception_handler(InvalidPriceError)
    async def invalid_price(request: Request, error: InvalidPriceError) -> JSONResponse:
        return _domain_problem(request, error, HTTPStatus.UNPROCESSABLE_ENTITY)

    @app.exception_handler(ExcessiveRefundError)
    async def excessive_refund(request: Request, error: ExcessiveRefundError) -> JSONResponse:
        return _domain_problem(request, error, HTTPStatus.UNPROCESSABLE_ENTITY)

    @app.exception_handler(UnsupportedExportFormatError)
    async def unsupported_export_format(
        request: Request, error: UnsupportedExportFormatError
    ) -> JSONResponse:
        return _domain_problem(request, error, HTTPStatus.UNPROCESSABLE_ENTITY)

    @app.exception_handler(InvalidOrderStateError)
    async def invalid_order_state(request: Request, error: InvalidOrderStateError) -> JSONResponse:
        return _domain_problem(request, error, HTTPStatus.CONFLICT, logging.WARNING)

    @app.exception_handler(CustomerHasOpenOrdersError)
    async def customer_has_open_orders(
        request: Request, error: CustomerHasOpenOrdersError
    ) -> JSONResponse:
        return _domain_problem(request, error, HTTPStatus.CONFLICT, logging.WARNING)

    @app.exception_handler(InvalidStoreCreditError)
    async def invalid_store_credit(
        request: Request, error: InvalidStoreCreditError
    ) -> JSONResponse:
        return _domain_problem(request, error, HTTPStatus.UNPROCESSABLE_ENTITY)

    @app.exception_handler(InvalidStatementPeriodError)
    async def invalid_statement_period(
        request: Request, error: InvalidStatementPeriodError
    ) -> JSONResponse:
        return _domain_problem(request, error, HTTPStatus.UNPROCESSABLE_ENTITY)

    @app.exception_handler(InvalidCurrencyError)
    async def invalid_currency(request: Request, error: InvalidCurrencyError) -> JSONResponse:
        return _domain_problem(request, error, HTTPStatus.UNPROCESSABLE_ENTITY)

    @app.exception_handler(DomainError)
    async def unmapped_domain_error(request: Request, error: DomainError) -> JSONResponse:
        logger.error(
            "Unmapped domain error %s while handling %s",
            type(error).__name__,
            request.url.path,
            exc_info=(type(error), error, error.__traceback__),
        )
        return _problem_response(
            dto.ProblemDetailsResponse(
                type="/problems/unmapped-domain-error",
                title="Unexpected domain failure",
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
                detail="The request could not be completed.",
                instance=request.url.path,
                code="unmapped-domain-error",
                context={},
            )
        )
