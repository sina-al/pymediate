"""Monthly-statement HTTP routes."""

from dependency_injector.wiring import inject
from fastapi import APIRouter

from shop.application.statements.create_monthly_statement import CreateMonthlyStatementRequest
from shop.openapi import dto
from shop.openapi.errors import DOMAIN_PROBLEM_RESPONSES
from shop.openapi.routes.dependencies import MediatorDependency

router = APIRouter(tags=["statements"])


@router.post(
    "/customers/{customer_id}/statements",
    response_model=dto.CreateMonthlyStatementResponse,
    responses=DOMAIN_PROBLEM_RESPONSES,
)
@inject
async def create_monthly_statement(
    customer_id: int,
    body: dto.CreateMonthlyStatementRequest,
    mediator: MediatorDependency,
) -> dto.CreateMonthlyStatementResponse:
    """Create a converted monthly statement through its own use case."""
    result = await mediator.send(
        CreateMonthlyStatementRequest(customer_id, body.year, body.month, body.currency)
    )
    return dto.CreateMonthlyStatementResponse(
        statement_id=result.statement_id,
        customer_id=result.customer_id,
        year=result.year,
        month=result.month,
        currency=result.currency,
        order_count=result.order_count,
        total_minor=result.total_minor,
        document_url=result.document_url,
    )
