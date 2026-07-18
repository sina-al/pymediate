"""Synchronous handler base class for the mediator pattern."""

from abc import ABC, abstractmethod
from typing import Any

from .._internal.handler import HandlerBaseMixin


class RequestHandler[RequestT](HandlerBaseMixin[RequestT], ABC):
    """Abstract base handler class for synchronous request processing.

    ``RequestHandler[RequestT]`` handles one exact ``Request`` class. Its
    ``__call__`` method must be synchronous, accept that exact request type, and
    annotate the response type declared by the request. PyMediate validates the
    declaration when Python defines the handler class and registers one handler
    class per request type.

    Type Parameters:
        RequestT: The type of request this handler processes.

    Examples:
        Defining a synchronous handler:
            ```python
            from dataclasses import dataclass

            from pymediate.sync import Request, RequestHandler

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
            ```

    Note:
        Use ``pymediate.RequestHandler`` for an asynchronous ``__call__``.

    Raises:
        InvalidHandlerSignatureError: If __call__ signature is invalid.
        InvalidRequestTypeError: If the request type does not declare a response type.
        ResponseTypeMismatchError: If return type doesn't match expected response.
        HandlerAlreadyRegisteredError: If the request type already has a handler class.

    """

    _is_async = False  # Mark this as a synchronous handler

    @abstractmethod
    def __call__(self, request: RequestT) -> Any:
        """Handle the request and return a response.

        Implement this method as
        ``def __call__(self, request: RequestType) -> ResponseType``.

        Args:
            request: The request to handle.

        Returns:
            The response, of the type declared by the request's `Request[ResponseType]`.

        Note:
            The request annotation must be the exact class named in
            ``RequestHandler[RequestT]``. The return annotation must equal the type
            declared by ``Request[ResponseT]``. These annotations are checked when
            Python defines the handler class; returned values are not inspected on
            each call.
        """
        ...
