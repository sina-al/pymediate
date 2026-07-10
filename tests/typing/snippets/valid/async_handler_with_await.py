"""Async handler with proper await usage - should pass mypy."""

import asyncio
from dataclasses import dataclass
from typing import override

from pymediate import Request, Services
from pymediate.aio import Handler, Mediator


@dataclass
class ProcessResponse:
    result: str


@dataclass
class ProcessRequest(Request[ProcessResponse]):
    data: str


async def async_operation(data: str) -> str:
    """Simulated async operation."""
    await asyncio.sleep(0.01)
    return data.upper()


class ProcessHandler(Handler[ProcessRequest]):
    @override
    async def __call__(self, request: ProcessRequest) -> ProcessResponse:
        # Properly await async operations
        result = await async_operation(request.data)
        return ProcessResponse(result=result)


async def main() -> None:
    provider = Services().add(ProcessHandler()).provider()
    mediator = Mediator(provider)

    response = await mediator.send(ProcessRequest(data="test"))
    assert response.result == "TEST"
