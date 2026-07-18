"""OpenTelemetry spans around application request dispatch."""

from collections.abc import Awaitable, Callable
from typing import Any

from opentelemetry.trace import Status, StatusCode, Tracer
from pymediate import PipelineBehavior, Request


class TracingBehavior(PipelineBehavior[Request[Any]]):
    """Create one low-cardinality internal span for each mediator request."""

    def __init__(self, tracer: Tracer) -> None:
        self._tracer = tracer

    async def __call__(self, request: Request[Any], next: Callable[[], Awaitable[Any]]) -> Any:
        request_type = type(request)
        with self._tracer.start_as_current_span(
            request_type.__name__,
            attributes={
                "shop.request.type": request_type.__name__,
                "shop.request.module": request_type.__module__,
            },
        ) as span:
            try:
                response = await next()
            except BaseException as error:
                span.record_exception(error)
                span.set_status(Status(StatusCode.ERROR, type(error).__name__))
                span.set_attribute("error.type", type(error).__name__)
                raise

            span.set_attribute("shop.response.type", type(response).__name__)
            return response
