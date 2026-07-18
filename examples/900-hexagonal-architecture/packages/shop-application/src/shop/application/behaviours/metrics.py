"""OpenTelemetry application request measurements."""

from collections.abc import Awaitable, Callable
from time import perf_counter
from typing import Any

from opentelemetry.metrics import Meter
from pymediate import PipelineBehavior, Request


class MetricsBehavior(PipelineBehavior[Request[Any]]):
    """Measure request count and duration using bounded attributes."""

    def __init__(self, meter: Meter, monotonic: Callable[[], float] = perf_counter) -> None:
        self._requests = meter.create_counter(
            "shop.application.requests",
            unit="{request}",
            description="Mediator requests completed by the shop application",
        )
        self._duration = meter.create_histogram(
            "shop.application.request.duration",
            unit="ms",
            description="Mediator request duration",
        )
        self._monotonic = monotonic

    async def __call__(self, request: Request[Any], next: Callable[[], Awaitable[Any]]) -> Any:
        request_name = type(request).__name__
        started_at = self._monotonic()
        try:
            response = await next()
        except BaseException as error:
            self._record(request_name, "error", started_at, type(error).__name__)
            raise

        self._record(request_name, "success", started_at)
        return response

    def _record(
        self,
        request_name: str,
        outcome: str,
        started_at: float,
        error_type: str | None = None,
    ) -> None:
        attributes = {"request.type": request_name, "request.outcome": outcome}
        if error_type is not None:
            attributes["error.type"] = error_type
        self._requests.add(1, attributes)
        self._duration.record((self._monotonic() - started_at) * 1_000, attributes)
