"""Request base class for the mediator pattern."""

from typing import Any

from ._internal import registry


class Request[ResponseT]:
    """Base class for a request that produces one typed response.

    Inherit from ``Request[ResponseT]`` to declare the type returned by the
    request's handler. This lets a static type checker infer the result of
    ``Mediator.send()``.

    PyMediate records the relationship when Python defines the request class and
    uses it to validate a handler's return annotation. It does not inspect the
    value returned by the handler at dispatch time.

    Type Parameters:
        ResponseT: The response type returned by the request's handler.

    Examples:
        Defining a dataclass request:
            ```python
            from dataclasses import dataclass

            from pymediate import Request

            @dataclass(frozen=True)
            class OrderReceipt:
                order_id: int
                summary: str

            @dataclass(frozen=True)
            class PlaceOrder(Request[OrderReceipt]):
                customer_id: int
                item: str
                quantity: int
            ```

    Note:
        A bare subclass such as ``class PlaceOrder(Request): ...`` has no recorded
        response type and cannot be paired with a valid ``RequestHandler``.
    """

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Register the response type when a Request subclass is created.

        This hook is automatically called when a new Request subclass is defined.
        It extracts the response type from the generic type parameter and stores
        it in the global registry for later validation.

        Args:
            **kwargs: Additional keyword arguments passed to parent __init_subclass__.

        Note:
            This method is called automatically by Python when a subclass is created.
            You should not call this method directly.
        """
        super().__init_subclass__(**kwargs)

        if orig_bases := getattr(cls, "__orig_bases__", None):
            for base in orig_bases:
                if getattr(base, "__origin__", None) is Request:
                    if args := getattr(base, "__args__", None):
                        response_type = args[0]
                        registry.register_request_response_type(cls, response_type)
                        break
