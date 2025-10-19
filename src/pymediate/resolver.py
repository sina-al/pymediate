"""Resolver protocol and implementations for dependency injection."""

from typing import TYPE_CHECKING, Any, Protocol, TypeVar

from pymediate.errors import HandlerNotFoundError, HandlerTypeMismatchError

if TYPE_CHECKING:
    from pymediate.handler import Handler

RequestType = TypeVar("RequestType")


class Resolver(Protocol):
    """Protocol for resolving handler instances from request types.

    This protocol defines the interface for handler resolution, enabling
    integration with various dependency injection frameworks, service
    locators, or custom resolution strategies.

    Any class implementing this protocol can be used with the Mediator,
    making PyMediate flexible and framework-agnostic.

    Examples:
        Custom resolver with dict-based lookup:
            ```python
            class MyResolver:
                def __init__(self):
                    self.handlers = {}

                def resolve(self, request_class: type) -> Handler:
                    return self.handlers[request_class]
            ```

        DI container integration:
            ```python
            class DIResolver:
                def __init__(self, container):
                    self.container = container

                def resolve(self, request_class: type) -> Handler:
                    return self.container.resolve(request_class)
            ```

    See Also:
        - SimpleResolver: Built-in dict-based implementation
        - DependencyInjectorResolver: Integration with dependency-injector library
    """

    def resolve(self, request_class: type[RequestType]) -> "Handler[RequestType]":
        """Resolve and return a handler instance for the given request type.

        Args:
            request_class: The request type class to resolve a handler for.

        Returns:
            A handler instance capable of processing the given request type.

        Raises:
            HandlerNotFoundError: If no handler can be resolved for the request type.
        """
        ...


class SimpleResolver:
    """Dict-based resolver implementation for simple use cases.

    This is a straightforward, lightweight implementation that stores handlers
    in a dictionary keyed by request type. It's suitable for applications that
    don't need the complexity of a full dependency injection container.

    The resolver performs type-safety validation at registration time to ensure
    handlers are properly matched with their request types, catching errors early.

    Attributes:
        _handlers: Internal dict mapping request types to handler instances.

    Examples:
        Basic registration:
            ```python
            resolver = SimpleResolver()
            resolver.register(CreateUserRequest, CreateUserHandler())

            handler = resolver.resolve(CreateUserRequest)
            response = handler(CreateUserRequest(username="alice"))
            ```

        Pre-populated initialization:
            ```python
            handlers = {
                CreateUserRequest: CreateUserHandler(),
                UpdateUserRequest: UpdateUserHandler(),
            }
            resolver = SimpleResolver(handlers)
            ```

        With mediator:
            ```python
            resolver = SimpleResolver()
            resolver.register(CreateUserRequest, CreateUserHandler())
            mediator = Mediator(resolver)
            ```

    Note:
        For applications with complex dependency graphs, consider using
        DependencyInjectorResolver instead, which integrates with the
        dependency-injector library.

    See Also:
        - Resolver: The protocol this class implements
        - DependencyInjectorResolver: DI container-based alternative
    """

    def __init__(self, handlers: dict[type, "Handler[Any]"] | None = None):
        """Initialize resolver with optional pre-populated handler mapping.

        Args:
            handlers: Optional dictionary mapping request types to handler instances.
                Each handler will be validated to ensure it handles the corresponding
                request type. If validation fails, a HandlerTypeMismatchError is raised.

        Raises:
            HandlerTypeMismatchError: If any handler doesn't match its request type.

        Examples:
            ```python
            # Empty resolver
            resolver = SimpleResolver()

            # Pre-populated resolver
            resolver = SimpleResolver({
                CreateUserRequest: CreateUserHandler(),
                DeleteUserRequest: DeleteUserHandler(),
            })
            ```
        """
        self._handlers: dict[type, Handler[Any]] = {}
        if handlers:
            for request_class, handler in handlers.items():
                self.register(request_class, handler)

    def register(self, request_class: type[RequestType], handler: "Handler[RequestType]") -> None:
        """Register a handler instance for a request type.

        This method validates that the handler is designed to handle the given
        request type before registering it. This catches type mismatches at
        registration time rather than at runtime.

        Args:
            request_class: The request class this handler will process.
            handler: A handler instance that handles the given request type.
                The handler must be an instance of a Handler[RequestType] subclass.

        Raises:
            HandlerTypeMismatchError: If the handler is designed for a different
                request type than the one being registered.

        Examples:
            ```python
            resolver = SimpleResolver()

            # Correct registration
            resolver.register(CreateUserRequest, CreateUserHandler())

            # This would raise HandlerTypeMismatchError:
            # resolver.register(CreateUserRequest, UpdateUserHandler())
            ```

        Note:
            The handler parameter should be an *instance*, not a class. If you
            need lazy instantiation, consider using DependencyInjectorResolver.
        """
        # Validate that the handler can handle this request type
        handler_request_type = getattr(type(handler), "_request_type", None)
        if handler_request_type is not None and handler_request_type != request_class:
            raise HandlerTypeMismatchError(type(handler), handler_request_type, request_class)
        self._handlers[request_class] = handler

    def resolve(self, request_class: type[RequestType]) -> "Handler[RequestType]":
        """Resolve and return a handler instance for the given request type.

        This is the main resolution method called by the Mediator to obtain
        a handler instance for processing a request.

        Args:
            request_class: The request class to find a handler for.

        Returns:
            The handler instance that was registered for this request type.

        Raises:
            HandlerNotFoundError: If no handler is registered for the request type.
                The error message includes a list of available handlers to help
                with debugging.

        Examples:
            ```python
            resolver.register(CreateUserRequest, CreateUserHandler())

            # Later...
            handler = resolver.resolve(CreateUserRequest)
            response = handler(CreateUserRequest(username="alice"))
            ```

        Note:
            This method returns the same handler instance that was registered.
            For new instances on each resolution, use DependencyInjectorResolver
            with Factory providers.
        """
        if request_class not in self._handlers:
            available = list(self._handlers.keys())
            raise HandlerNotFoundError(request_class, available)
        return self._handlers[request_class]
