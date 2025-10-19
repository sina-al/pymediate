"""Resolver protocol and implementations for dependency injection."""

from typing import TYPE_CHECKING, Any, Protocol, TypeVar

from pymediate.errors import HandlerNotFoundError, HandlerTypeMismatchError

if TYPE_CHECKING:
    from pymediate.handler import Handler

RequestType = TypeVar("RequestType")


class Resolver(Protocol):
    """Protocol for resolving handler instances from request types.

    This allows integration with various DI frameworks like dependency-injector.

    Example:
        class MyResolver:
            def resolve(self, request_class: type) -> Handler:
                # Custom resolution logic
                return my_container.resolve(request_class)
    """

    def resolve(self, request_class: type[RequestType]) -> "Handler[RequestType]":
        """Resolve and return a handler instance for the given request type."""
        ...


class SimpleResolver:
    """Concrete resolver implementation using a simple dict-based registry.

    This is a basic implementation suitable for simple use cases.
    For more complex scenarios, use a DI container-based resolver.

    The resolver is type-safe: handlers are validated at registration time
    to ensure they properly handle their declared request types.

    Example:
        resolver = SimpleResolver()
        resolver.register(MyRequest, MyHandler())

        handler = resolver.resolve(MyRequest)
    """

    def __init__(self, handlers: dict[type, "Handler[Any]"] | None = None):
        """Initialize with a mapping of request types to handler instances.

        Args:
            handlers: Optional pre-populated dict of request types to handlers.
                     Each handler will be validated to ensure it handles the
                     corresponding request type.
        """
        self._handlers: dict[type, Handler[Any]] = {}
        if handlers:
            for request_class, handler in handlers.items():
                self.register(request_class, handler)

    def register(self, request_class: type[RequestType], handler: "Handler[RequestType]") -> None:
        """Register a handler instance for a request type.

        Args:
            request_class: The request class this handler will handle.
            handler: A handler instance that handles the given request type.
                    The handler must be an instance of Handler[RequestType].

        Raises:
            TypeError: If the handler doesn't properly handle the request type.
        """
        # Validate that the handler can handle this request type
        handler_request_type = getattr(type(handler), "_request_type", None)
        if handler_request_type is not None and handler_request_type != request_class:
            raise HandlerTypeMismatchError(type(handler), handler_request_type, request_class)
        self._handlers[request_class] = handler

    def resolve(self, request_class: type[RequestType]) -> "Handler[RequestType]":
        """Resolve and return a handler instance for the given request type.

        Args:
            request_class: The request class to find a handler for.

        Returns:
            The handler instance registered for this request type.

        Raises:
            ValueError: If no handler is registered for the request type.
        """
        if request_class not in self._handlers:
            available = list(self._handlers.keys())
            raise HandlerNotFoundError(request_class, available)
        return self._handlers[request_class]
