"""Customer-account HTTP routes."""

from dependency_injector.wiring import inject
from fastapi import APIRouter, Response, status

from shop.application.customers.adjust_store_credit import AdjustStoreCreditRequest
from shop.application.customers.close_customer_account import CloseCustomerAccountRequest
from shop.application.customers.open_customer_account import OpenCustomerAccountRequest
from shop.openapi import dto
from shop.openapi.errors import DOMAIN_PROBLEM_RESPONSES
from shop.openapi.routes.dependencies import MediatorDependency

router = APIRouter(tags=["customers"])


@router.post(
    "/customers",
    response_model=dto.OpenCustomerAccountResponse,
    status_code=status.HTTP_201_CREATED,
    responses=DOMAIN_PROBLEM_RESPONSES,
)
@inject
async def open_customer_account(
    body: dto.OpenCustomerAccountRequest,
    mediator: MediatorDependency,
) -> dto.OpenCustomerAccountResponse:
    """Open a customer account explicitly before using customer capabilities."""
    result = await mediator.send(OpenCustomerAccountRequest(body.customer_id))
    return dto.OpenCustomerAccountResponse(
        customer_id=result.customer_id,
        store_credit_pence=result.store_credit_pence,
    )


@router.delete(
    "/customers/{customer_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=DOMAIN_PROBLEM_RESPONSES,
)
@inject
async def close_customer_account(
    customer_id: int,
    mediator: MediatorDependency,
) -> Response:
    """Close an account only after the orders context reports no open work."""
    await mediator.send(CloseCustomerAccountRequest(customer_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/customers/{customer_id}/store-credit",
    response_model=dto.AdjustStoreCreditResponse,
    responses=DOMAIN_PROBLEM_RESPONSES,
)
@inject
async def adjust_store_credit(
    customer_id: int,
    body: dto.AdjustStoreCreditRequest,
    mediator: MediatorDependency,
) -> dto.AdjustStoreCreditResponse:
    """Add store credit through the customer-owned use case."""
    result = await mediator.send(AdjustStoreCreditRequest(customer_id, body.amount_pence))
    return dto.AdjustStoreCreditResponse(
        customer_id=result.customer_id,
        store_credit_pence=result.store_credit_pence,
    )
