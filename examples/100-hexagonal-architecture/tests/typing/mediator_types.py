"""Static assertions for mediator response inference at the application seam."""

from typing import assert_type

from pymediate import Mediator

from shop.application.invoices.get_invoice import GetInvoiceRequest, GetInvoiceResponse
from shop.application.orders.create_order import CreateOrderRequest, CreateOrderResponse
from shop.application.orders.export_orders import ExportOrdersRequest, ExportOrdersResponse
from shop.application.statements.create_monthly_statement import (
    CreateMonthlyStatementRequest,
    CreateMonthlyStatementResponse,
)


async def mediator_return_types(mediator: Mediator) -> None:
    """Keep return inference intact at the application seam."""
    assert_type(await mediator.send(CreateOrderRequest(7, ())), CreateOrderResponse)
    assert_type(await mediator.send(ExportOrdersRequest(7)), ExportOrdersResponse)
    assert_type(await mediator.send(GetInvoiceRequest(1)), GetInvoiceResponse)
    assert_type(
        await mediator.send(CreateMonthlyStatementRequest(7, 2026, 7)),
        CreateMonthlyStatementResponse,
    )
