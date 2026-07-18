"""Order HTTP routes and transport-to-application translation."""

from dependency_injector.wiring import inject
from fastapi import APIRouter, status

from shop.application.orders.cancel_order import CancelOrderRequest
from shop.application.orders.create_order import CreateOrderRequest
from shop.application.orders.get_order_history import GetOrderHistoryRequest
from shop.application.orders.refund_order import RefundOrderRequest
from shop.application.orders.request_order_export import RequestOrderExportRequest
from shop.domain.entities.orders import OrderItem
from shop.openapi import dto
from shop.openapi.errors import DOMAIN_PROBLEM_RESPONSES
from shop.openapi.routes.dependencies import MediatorDependency

router = APIRouter(tags=["orders"])


@router.post(
    "/orders",
    response_model=dto.CreateOrderResponse,
    status_code=status.HTTP_201_CREATED,
    responses=DOMAIN_PROBLEM_RESPONSES,
)
@inject
async def create_order(
    body: dto.CreateOrderRequest, mediator: MediatorDependency
) -> dto.CreateOrderResponse:
    """Place an order through the mediator."""
    request = CreateOrderRequest(
        body.customer_id,
        tuple(OrderItem(item.sku, item.quantity) for item in body.items),
    )
    result = await mediator.send(request)
    return dto.CreateOrderResponse(
        order_id=result.order_id,
        customer_id=result.customer_id,
        total_pence=result.total_pence,
        refunded_pence=result.refunded_pence,
        status=result.status,
    )


@router.get(
    "/orders/{order_id}/history",
    response_model=dto.GetOrderHistoryResponse,
)
@inject
async def get_order_history(
    order_id: int, mediator: MediatorDependency
) -> dto.GetOrderHistoryResponse:
    """Return an allowlisted public projection of an order's business history."""
    result = await mediator.send(GetOrderHistoryRequest(order_id))
    return dto.GetOrderHistoryResponse(
        order_id=result.order_id,
        entries=[
            dto.OrderHistoryEntryResponse(
                event_id=entry.event_id,
                kind=entry.kind,
                occurred_at=entry.occurred_at,
                amount_pence=entry.amount_pence,
                refunded_pence=entry.refunded_pence,
                status=entry.status,
            )
            for entry in result.entries
        ],
    )


@router.post(
    "/orders/{order_id}/refund",
    response_model=dto.RefundOrderResponse,
    responses=DOMAIN_PROBLEM_RESPONSES,
)
@inject
async def refund_order(
    order_id: int, body: dto.RefundOrderRequest, mediator: MediatorDependency
) -> dto.RefundOrderResponse:
    """Refund an order."""
    result = await mediator.send(RefundOrderRequest(order_id, body.amount_pence))
    return dto.RefundOrderResponse(
        order_id=result.order_id,
        customer_id=result.customer_id,
        total_pence=result.total_pence,
        refunded_pence=result.refunded_pence,
        status=result.status,
    )


@router.post(
    "/orders/{order_id}/cancel",
    response_model=dto.CancelOrderResponse,
    responses=DOMAIN_PROBLEM_RESPONSES,
)
@inject
async def cancel_order(order_id: int, mediator: MediatorDependency) -> dto.CancelOrderResponse:
    """Cancel an order and release its external reservations."""
    result = await mediator.send(CancelOrderRequest(order_id))
    return dto.CancelOrderResponse(
        order_id=result.order_id,
        customer_id=result.customer_id,
        total_pence=result.total_pence,
        refunded_pence=result.refunded_pence,
        status=result.status,
    )


@router.post(
    "/orders/exports/{customer_id}",
    response_model=dto.RequestOrderExportResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses=DOMAIN_PROBLEM_RESPONSES,
)
@inject
async def request_order_export(
    customer_id: int,
    mediator: MediatorDependency,
    format: str = "csv",
) -> dto.RequestOrderExportResponse:
    """Queue an export without borrowing the HTTP request lifecycle."""
    result = await mediator.send(RequestOrderExportRequest(customer_id, format))
    return dto.RequestOrderExportResponse(job_id=result.job_id, customer_id=result.customer_id)
