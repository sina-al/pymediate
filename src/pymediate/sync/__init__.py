"""Synchronous API for PyMediate.

This package is the sync mirror of the async top-level API: the same names,
with plain `def` handlers and a blocking `send()`/`publish()`. Shared names
(`Request`, `Event`, `Services`, `ServiceProvider`, and every error) are
re-exported here as the identical top-level objects, so sync code needs one
import line.

Example:
    ```python
    from dataclasses import dataclass
    from pymediate.sync import Mediator, Request, RequestHandler, Services

    @dataclass
    class MyResponse:
        value: str

    @dataclass
    class MyRequest(Request[MyResponse]):
        data: str

    class MyHandler(RequestHandler[MyRequest]):
        def __call__(self, request: MyRequest) -> MyResponse:
            return MyResponse(value=request.data.upper())

    services = Services()
    services.add(MyHandler())
    mediator = Mediator(services.provider())
    response = mediator.send(MyRequest(data="test"))
    ```

Note:
    Handlers and Mediators from this package are sync-only. For asynchronous
    operations, use `from pymediate import RequestHandler, Mediator` instead.
"""

from ..errors import (
    HandlerAlreadyRegisteredError,
    HandlerNotFoundError,
    InvalidEventTypeError,
    InvalidHandlerSignatureError,
    InvalidRequestTypeError,
    PyMediateError,
    ResponseTypeMismatchError,
)
from ..event import Event
from ..request import Request
from ..service import ServiceNotFoundError, ServiceProvider, Services
from .event import EventHandler
from .handler import RequestHandler
from .mediator import Mediator
from .pipeline import PipelineBehavior

__all__ = [
    "Request",
    "RequestHandler",
    "Mediator",
    # Events
    "Event",
    "EventHandler",
    # Service Provider
    "ServiceProvider",
    "Services",
    "ServiceNotFoundError",
    # Pipeline
    "PipelineBehavior",
    # Errors
    "PyMediateError",
    "HandlerNotFoundError",
    "HandlerAlreadyRegisteredError",
    "InvalidHandlerSignatureError",
    "InvalidRequestTypeError",
    "InvalidEventTypeError",
    "ResponseTypeMismatchError",
]
