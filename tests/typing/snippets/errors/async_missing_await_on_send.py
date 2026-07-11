"""Missing await on mediator.send() - should fail mypy."""

import asyncio
from dataclasses import dataclass
from typing import override

from pymediate import Mediator, Request, RequestHandler, Services


@dataclass
class Response:
    value: int


@dataclass
class MyRequest(Request[Response]):
    data: int


class MyHandler(RequestHandler[MyRequest]):
    @override
    async def __call__(self, request: MyRequest) -> Response:
        await asyncio.sleep(0.01)
        return Response(value=request.data * 2)


async def main() -> None:
    provider = Services().add(MyHandler()).provider()
    mediator = Mediator(provider)

    # ERROR: Missing await - returns coroutine, not Response
    mediator.send(MyRequest(data=10))

    # This should fail - trying to access attribute on coroutine
