"""Pipeline with multiple behaviors - type inference should work correctly."""

from collections.abc import Callable
from dataclasses import dataclass

from pymediate import Handler, Request
from pymediate.pipeline import Pipeline, PipelineBehavior


@dataclass
class OrderResponse:
    order_id: int
    total: float


@dataclass
class CreateOrderRequest(Request[OrderResponse]):
    items: list[str]


class CreateOrderHandler(Handler[CreateOrderRequest]):
    def __call__(self, request: CreateOrderRequest) -> OrderResponse:
        return OrderResponse(order_id=100, total=50.0)


class LoggingBehavior(PipelineBehavior[CreateOrderRequest, OrderResponse]):
    def __call__(
        self,
        request: CreateOrderRequest,
        next: Callable[[], OrderResponse],
    ) -> OrderResponse:
        print(f"Logging: {len(request.items)} items")
        return next()


class TimingBehavior(PipelineBehavior[CreateOrderRequest, OrderResponse]):
    def __call__(
        self,
        request: CreateOrderRequest,
        next: Callable[[], OrderResponse],
    ) -> OrderResponse:
        print("Timing started")
        response = next()
        print("Timing ended")
        return response


class ValidationBehavior(PipelineBehavior[CreateOrderRequest, OrderResponse]):
    def __call__(
        self,
        request: CreateOrderRequest,
        next: Callable[[], OrderResponse],
    ) -> OrderResponse:
        if not request.items:
            raise ValueError("No items")
        return next()


# Create pipeline with multiple behaviors
handler = CreateOrderHandler()
pipeline: Pipeline[CreateOrderRequest, OrderResponse] = Pipeline(
    [
        LoggingBehavior(),
        TimingBehavior(),
        ValidationBehavior(),
    ],
    handler,
)

request = CreateOrderRequest(items=["item1", "item2"])
response = pipeline(request)

# Type checking - mypy should know these fields exist
order_id: int = response.order_id
total: float = response.total
