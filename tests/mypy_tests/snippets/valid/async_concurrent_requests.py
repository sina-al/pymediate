"""Concurrent async requests with asyncio.gather() - should pass mypy."""

import asyncio
from dataclasses import dataclass

from pymediate import Request, SimpleResolver
from pymediate.aio import Handler, Mediator


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


class Handler1(Handler[Request1]):
    async def __call__(self, request: Request1) -> Response1:
        await asyncio.sleep(0.01)
        return Response1(value=request.data * 2)


class Handler2(Handler[Request2]):
    async def __call__(self, request: Request2) -> Response2:
        await asyncio.sleep(0.01)
        return Response2(message=request.text.upper())


async def main() -> None:
    resolver = SimpleResolver()
    resolver.register(Request1, Handler1())
    resolver.register(Request2, Handler2())
    mediator = Mediator(resolver)

    # Type inference with asyncio.gather()
    responses = await asyncio.gather(
        mediator.send(Request1(data=10)),
        mediator.send(Request2(text="hello")),
    )

    # Mypy should know the types
    resp1 = responses[0]
    resp2 = responses[1]

    val: int = resp1.value
    msg: str = resp2.message
