"""Missing await on mediator.send() - should fail mypy."""

import asyncio
from dataclasses import dataclass

from pymediate import Request, ServiceCollection
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
    services = ServiceCollection()
    services.add(MyRequest, MyHandler())
    provider = services.build_provider()
    mediator = Mediator(provider)

    # ERROR: Missing await - returns coroutine, not Response
    mediator.send(MyRequest(data=10))

    # This should fail - trying to access attribute on coroutine
