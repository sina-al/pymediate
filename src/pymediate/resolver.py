"""Resolver protocol and implementations for dependency injection."""

from typing import Any, Protocol, TypeVar

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

    def resolve(self, request_class: type[RequestType]) -> Any:  # Handler[RequestType]
        """Resolve and return a handler instance for the given request type."""
        ...


class SimpleResolver:
    """Concrete resolver implementation using a simple dict-based registry.

    This is a basic implementation suitable for simple use cases.
    For more complex scenarios, use a DI container-based resolver.

    Example:
        resolver = SimpleResolver()
        resolver.register(MyRequest, MyHandler())

        handler = resolver.resolve(MyRequest)
    """

    def __init__(self, handlers: dict[type, Any] | None = None):
        """Initialize with a mapping of request types to handler instances."""
        self._handlers = handlers or {}

    def register(self, request_class: type, handler: Any) -> None:
        """Register a handler instance for a request type."""
        self._handlers[request_class] = handler

    def resolve(self, request_class: type[RequestType]) -> Any:  # Handler[RequestType]
        """Resolve and return a handler instance for the given request type."""
        if request_class not in self._handlers:
            raise ValueError(f"No handler registered for request type {request_class.__name__}")
        return self._handlers[request_class]
