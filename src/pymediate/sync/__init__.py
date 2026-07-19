"""Synchronous API for PyMediate.

This package mirrors the asynchronous top-level API with synchronous handlers,
pipeline behaviors, and mediator methods. Shared message, service, and error
types are re-exported as the same objects in both namespaces.

Examples:
    ```python
    from dataclasses import dataclass
    from pymediate.sync import Mediator, Request, RequestHandler, Services

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
        def __call__(self, request: PlaceOrder) -> OrderReceipt:
            return OrderReceipt(
                order_id=42,
                summary=f"{request.quantity} × {request.item}",
            )

    services = Services().add(PlaceOrderHandler())
    mediator = Mediator(services=services.provider())
    receipt = mediator.send(PlaceOrder(customer_id=7, item="tea", quantity=2))
    ```

Note:
    Handler, mediator, and pipeline variants in this package are synchronous.
    Import their asynchronous variants from ``pymediate``.
"""

from ..errors import (
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
from ..event import Event
from ..request import Request
from ..service import ServiceNotFoundError, ServiceProvider, Services
from ..stream import StreamRequest
from .event import EventHandler
from .handler import RequestHandler
from .mediator import Mediator
from .pipeline import Next, PipelineBehavior
from .stream import StreamRequestHandler

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
