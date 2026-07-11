"""Concurrent async requests with asyncio.gather() - should pass mypy."""

import asyncio
from dataclasses import dataclass
from typing import override

from pymediate import Request, Services
from pymediate.aio import Mediator, RequestHandler


@dataclass
class Response1:
    value: int


@dataclass
class Response2:
    message: str


@dataclass
class Request1(Request[Response1]):
    data: int


@dataclass
class Request2(Request[Response2]):
    text: str


class Handler1(RequestHandler[Request1]):
    @override
    async def __call__(self, request: Request1) -> Response1:
        await asyncio.sleep(0.01)
        return Response1(value=request.data * 2)


class Handler2(RequestHandler[Request2]):
    @override
    async def __call__(self, request: Request2) -> Response2:
        await asyncio.sleep(0.01)
        return Response2(message=request.text.upper())


async def main() -> None:
    provider = Services().add(Handler1()).add(Handler2()).provider()
    mediator = Mediator(provider)

    # Type inference with asyncio.gather()
    responses = await asyncio.gather(
        mediator.send(Request1(data=10)),
        mediator.send(Request2(text="hello")),
    )

    # Mypy should know the types
    responses[0]
    responses[1]
