"""Structured lifecycle logging around every application request."""

from collections.abc import Awaitable, Callable
from time import perf_counter
from typing import Any

from pymediate import PipelineBehavior, Request

from shop.ports.logger import Logger


class LoggerBehavior(PipelineBehavior[Request[Any]]):
    """Log request start, completion, and failure without exposing request payloads."""

    def __init__(self, logger: Logger, monotonic: Callable[[], float] = perf_counter) -> None:
        self._logger = logger
        self._monotonic = monotonic

    async def __call__(self, request: Request[Any], next: Callable[[], Awaitable[Any]]) -> Any:
        request_type = type(request)
        metadata: dict[str, object] = {
            "request_type": request_type.__name__,
            "request_module": request_type.__module__,
        }
        started_at = self._monotonic()
        self._logger.info("request.started", **metadata)

        try:
            response = await next()
        except BaseException as error:
            self._logger.error(
                "request.failed",
                **metadata,
                duration_ms=self._duration_ms(started_at),
                error_type=type(error).__name__,
            )
            raise

        self._logger.info(
            "request.completed",
            **metadata,
            duration_ms=self._duration_ms(started_at),
            response_type=type(response).__name__,
        )
        return response

    def _duration_ms(self, started_at: float) -> float:
        return round((self._monotonic() - started_at) * 1_000, 3)
