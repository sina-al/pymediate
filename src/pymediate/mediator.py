"""Mediator implementation for routing requests to handlers."""

from pymediate.request import Request
from pymediate.resolver import Resolver


class Mediator:
    """Mediator that routes requests to their handlers using a resolver.

    The mediator uses a resolver to obtain handler instances and delegates
    request handling to them. The return type of send() is properly typed
    based on the request's response type.

    Example:
        resolver = SimpleResolver()
        resolver.register(MyRequest, MyHandler())

        mediator = Mediator(resolver)
        response = mediator.send(MyRequest("data"))  # response is typed as MyResponse
    """

    def __init__(self, resolver: Resolver) -> None:
        """Initialize with a resolver for obtaining handler instances."""
        self._resolver = resolver

    def send[ResponseT](self, request: Request[ResponseT]) -> ResponseT:
        """Send a request and get the response.

        The response type is inferred from the request's type parameter.

        Args:
            request: The request instance to send

        Returns:
            The response from the handler, properly typed

        Raises:
            ValueError: If no handler is registered for the request type
        """
        request_type = type(request)
        handler = self._resolver.resolve(request_type)
        return handler(request)  # type: ignore[no-any-return]
