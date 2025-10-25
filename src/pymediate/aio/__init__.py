"""Async support for PyMediate.

This package provides asynchronous variants of Handler and Mediator for
use with async/await syntax.

Example:
    ```python
    from pymediate.aio import Handler, Mediator
    from pymediate import Request

    class MyResponse:
        value: str

    class MyRequest(Request[MyResponse]):
        data: str

    class MyHandler(Handler[MyRequest]):
        async def __call__(self, request: MyRequest) -> MyResponse:
            # Can use await here
            result = await some_async_operation(request.data)
            return MyResponse(value=result)

    mediator = Mediator(resolver)
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
