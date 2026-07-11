"""A reusable generic behavior scoped by subclassing narrows the request type - passes mypy."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, override

from pymediate import Mediator, PipelineBehavior, Request, RequestHandler, Services


@dataclass
class OrderResponse:
    order_id: int


@dataclass
class CreateOrder(Request[OrderResponse]):
    item: str


class CreateOrderHandler(RequestHandler[CreateOrder]):
    @override
    async def __call__(self, request: CreateOrder) -> OrderResponse:
        return OrderResponse(order_id=1)


# A reusable, batteries-included-style generic behavior. Callers scope it by subclassing.
class RetryBehavior[RequestT: Request[Any]](PipelineBehavior[RequestT]):
    @override
    async def __call__(self, request: RequestT, next: Callable[[], Awaitable[object]]) -> object:
        return await next()


# Scoping the reusable behavior to a concrete request narrows `request` in __call__.
class OrderRetry(RetryBehavior[CreateOrder]):
    @override
    async def __call__(self, request: CreateOrder, next: Callable[[], Awaitable[object]]) -> object:
        item: str = request.item  # statically narrowed to CreateOrder
        assert item
        return await next()


async def main() -> None:
    provider = Services().add(OrderRetry()).add(CreateOrderHandler()).provider()
    mediator = Mediator(provider)
    response = await mediator.send(CreateOrder(item="widget"))
    order_id: int = response.order_id
    assert order_id == 1
