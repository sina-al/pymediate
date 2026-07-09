"""Multiple typed behaviors around one handler - type inference should work correctly."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from pymediate import Handler, Mediator, PipelineBehavior, Request, Services


@dataclass
class OrderResponse:
    order_id: int
    total: float


@dataclass
class CreateOrderRequest(Request[OrderResponse]):
    items: list[str]


class CreateOrderHandler(Handler[CreateOrderRequest]):
    @override
    def __call__(self, request: CreateOrderRequest) -> OrderResponse:
        return OrderResponse(order_id=100, total=50.0)


class LoggingBehavior(PipelineBehavior[CreateOrderRequest]):
    @override
    def __call__(
        self,
        request: CreateOrderRequest,
        next: Callable[[], OrderResponse],
    ) -> OrderResponse:
        print(f"Logging: {len(request.items)} items")
        return next()


class TimingBehavior(PipelineBehavior[CreateOrderRequest]):
    @override
    def __call__(
        self,
        request: CreateOrderRequest,
        next: Callable[[], OrderResponse],
    ) -> OrderResponse:
        print("Timing started")
        response = next()
        print("Timing ended")
        return response


class ValidationBehavior(PipelineBehavior[CreateOrderRequest]):
    @override
    def __call__(
        self,
        request: CreateOrderRequest,
        next: Callable[[], OrderResponse],
    ) -> OrderResponse:
        if not request.items:
            raise ValueError("No items")
        return next()


# Register several behaviors; first registered is the outermost wrapper
provider = (
    Services()
    .add(LoggingBehavior())
    .add(TimingBehavior())
    .add(ValidationBehavior())
    .add(CreateOrderHandler())
    .provider()
)
mediator = Mediator(provider)

request = CreateOrderRequest(items=["item1", "item2"])
response = mediator.send(request)

# Type checking - mypy should know these fields exist
order_id: int = response.order_id
total: float = response.total
