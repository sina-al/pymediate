"""Async support for PyMediate.

This package provides asynchronous variants of RequestHandler, EventHandler, and
Mediator for use with async/await syntax.

Example:
    ```python
    from dataclasses import dataclass
    from pymediate import Request, Services
    from pymediate.aio import RequestHandler, Mediator

    @dataclass
    class MyResponse:
        value: str

    @dataclass
    class MyRequest(Request[MyResponse]):
        data: str

    class MyHandler(RequestHandler[MyRequest]):
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
    operations, use `from pymediate import RequestHandler, Mediator` instead.
"""

import warnings
from typing import Any

from .event import EventHandler
from .handler import RequestHandler
from .mediator import Mediator
from .pipeline import PipelineBehavior

__all__ = ["EventHandler", "Mediator", "PipelineBehavior", "RequestHandler"]


def __getattr__(name: str) -> Any:
    """Serve the deprecated ``Handler`` alias with a warning (see ADR 0006)."""
    if name == "Handler":
        warnings.warn(
            "pymediate.aio.Handler was renamed to RequestHandler in 0.4.0; "
            "the Handler alias will be removed in the next minor release.",
            DeprecationWarning,
            stacklevel=2,
        )
        return RequestHandler
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
