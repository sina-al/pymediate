"""Typed request dispatch, streaming, and event publication for Python 3.12+.

The top-level package provides the asynchronous API. Synchronous
``RequestHandler``, ``EventHandler``, ``StreamRequestHandler``, ``Mediator``, and
``PipelineBehavior`` variants live in ``pymediate.sync``; message types,
services, and errors are shared between the two namespaces.

Requests declare their response type with ``Request[ResponseT]``. A matching
``RequestHandler[RequestT]`` supplies that response, and ``Mediator.send()``
preserves the relationship for static type checkers. PyMediate validates handler
annotations when Python defines the handler class. It does not inspect each value
returned at dispatch time.

Examples:
    ```python
    import asyncio
    from dataclasses import dataclass

    from pymediate import Mediator, Request, RequestHandler, Services

    @dataclass(frozen=True)
    class OrderReceipt:
        order_id: int
        summary: str

    @dataclass(frozen=True)
    class PlaceOrder(Request[OrderReceipt]):
        customer_id: int
        item: str
        quantity: int

    class PlaceOrderHandler(RequestHandler[PlaceOrder]):
        async def __call__(self, request: PlaceOrder) -> OrderReceipt:
            return OrderReceipt(
                order_id=42,
                summary=f"{request.quantity} × {request.item}",
            )

    async def main() -> None:
        services = Services().add(PlaceOrderHandler())
        mediator = Mediator(services=services.provider())

        receipt = await mediator.send(
            PlaceOrder(customer_id=7, item="tea", quantity=2),
        )
        print(receipt.order_id)

    asyncio.run(main())
    ```

Documentation: https://pymediate.sina-al.uk
"""

from importlib.metadata import PackageNotFoundError, version

from .errors import (
    HandlerAlreadyRegisteredError,
    HandlerNotFoundError,
    InvalidEventTypeError,
    InvalidHandlerSignatureError,
    InvalidPipelineBehaviorsError,
    InvalidRequestTypeError,
    InvalidStreamRequestTypeError,
    PyMediateError,
    ResponseTypeMismatchError,
)
from .event import Event, EventHandler
from .handler import RequestHandler
from .mediator import Mediator
from .pipeline import Next, PipelineBehavior
from .request import Request
from .service import ServiceNotFoundError, ServiceProvider, Services
from .stream import StreamRequest, StreamRequestHandler

__all__ = [
    "Request",
    "RequestHandler",
    "Mediator",
    # Events
    "Event",
    "EventHandler",
    # Streaming
    "StreamRequest",
    "StreamRequestHandler",
    # Service Provider
    "ServiceProvider",
    "Services",
    "ServiceNotFoundError",
    # Pipeline
    "PipelineBehavior",
    "Next",
    # Errors
    "PyMediateError",
    "HandlerNotFoundError",
    "HandlerAlreadyRegisteredError",
    "InvalidHandlerSignatureError",
    "InvalidPipelineBehaviorsError",
    "InvalidRequestTypeError",
    "InvalidEventTypeError",
    "InvalidStreamRequestTypeError",
    "ResponseTypeMismatchError",
]

# The distribution version is derived from git tags at build time (hatch-vcs); the
# installed package metadata is the only source of truth for it at runtime.
try:
    __version__ = version("pymediate")
except PackageNotFoundError:  # pragma: no cover - source tree used without an install
    __version__ = "0.0.0+unknown"
