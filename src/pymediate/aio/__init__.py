"""Async support for PyMediate.

This package provides asynchronous variants of Handler and Mediator for
use with async/await syntax.

Example:
    ```python
    from dataclasses import dataclass
    from pymediate import Request, Services
    from pymediate.aio import Handler, Mediator

    @dataclass
    class MyResponse:
        value: str

    @dataclass
    class MyRequest(Request[MyResponse]):
        data: str

    class MyHandler(Handler[MyRequest]):
        async def __call__(self, request: MyRequest) -> MyResponse:
            result = await some_async_operation(request.data)
            return MyResponse(value=result)

    services = Services()
    services.add(MyHandler())
    mediator = Mediator(services.provider())
    response = await mediator.send(MyRequest(data="test"))
    ```

Note:
    Handlers and Mediators from this package are async-only. For synchronous
    operations, use `from pymediate import Handler, Mediator` instead.
"""

from .handler import Handler
from .mediator import Mediator
from .pipeline import PipelineBehavior

__all__ = ["Handler", "Mediator", "PipelineBehavior"]
