"""Invoice query HTTP routes."""

from dependency_injector.wiring import inject
from fastapi import APIRouter

from shop.application.invoices.get_invoice import GetInvoiceRequest
from shop.openapi import dto
from shop.openapi.errors import DOMAIN_PROBLEM_RESPONSES
from shop.openapi.routes.dependencies import MediatorDependency

router = APIRouter(prefix="/invoices", tags=["invoices"])


@router.get(
    "/orders/{order_id}",
    response_model=dto.GetInvoiceResponse,
    responses=DOMAIN_PROBLEM_RESPONSES,
)
@inject
async def get_invoice(order_id: int, mediator: MediatorDependency) -> dto.GetInvoiceResponse:
    """Retrieve the invoice produced from an integration message."""
    result = await mediator.send(GetInvoiceRequest(order_id))
    return dto.GetInvoiceResponse(
        invoice_id=result.invoice_id,
        order_id=result.order_id,
        customer_id=result.customer_id,
        total_pence=result.total_pence,
        document_url=result.document_url,
    )
