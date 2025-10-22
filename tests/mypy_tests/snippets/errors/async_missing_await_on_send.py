"""Missing await on mediator.send() - should fail mypy."""

import asyncio
from dataclasses import dataclass

from pymediate import Request, SimpleResolver
from pymediate.aio import Handler, Mediator


@dataclass
class Response:
    value: int


@dataclass
class MyRequest(Request[Response]):
    data: int


class MyHandler(Handler[MyRequest]):
    async def __call__(self, request: MyRequest) -> Response:
        await asyncio.sleep(0.01)
        return Response(value=request.data * 2)


async def main() -> None:
    resolver = SimpleResolver()
    resolver.register(MyRequest, MyHandler())
    mediator = Mediator(resolver)

    # ERROR: Missing await - returns coroutine, not Response
    response = mediator.send(MyRequest(data=10))

    # This should fail - trying to access attribute on coroutine
    value: int = response.value
