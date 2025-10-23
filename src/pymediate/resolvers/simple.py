"""Simple dict-based resolver implementation."""

from typing import TYPE_CHECKING, Any

from .. import errors

if TYPE_CHECKING:
    from ..handler import Handler


class SimpleResolver:
    """Dict-based resolver implementation for simple use cases.

    This is a straightforward, lightweight implementation that stores handlers
    in a dictionary keyed by handler type. It's suitable for applications that
    don't need the complexity of a full dependency injection container.

    The resolver is responsible solely for instantiating/retrieving handler
    instances from handler types. The mediator handles request-to-handler-type
    mapping via the registry.

    Attributes:
        _handlers: Internal dict mapping handler types to handler instances.

    Examples:
        Basic registration:
            ```python
            resolver = SimpleResolver()
            resolver.register(CreateUserHandler())

            # Mediator will call resolver.resolve(CreateUserHandler)
            mediator = Mediator(resolver)
            response = mediator.send(CreateUserRequest(username="alice"))
            ```

        Pre-populated initialization:
            ```python
            handlers = [
                CreateUserHandler(),
                UpdateUserHandler(),
            ]
            resolver = SimpleResolver(handlers)
            ```

        With mediator:
            ```python
            resolver = SimpleResolver()
            resolver.register(CreateUserHandler())
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

    def __init__(self, handlers: list["Handler[Any]"] | None = None):
        """Initialize resolver with optional pre-populated handlers.

        Args:
            handlers: Optional list of handler instances to register.

        Examples:
            ```python
            # Empty resolver
            resolver = SimpleResolver()

            # Pre-populated resolver
            resolver = SimpleResolver([
                CreateUserHandler(),
                DeleteUserHandler(),
            ])
            ```
        """
        self._handlers: dict[type[Handler[Any]], Handler[Any]] = {}
        if handlers:
            for handler in handlers:
                self.register(handler)

    def register(self, handler: "Handler[Any]") -> None:
        """Register a handler instance.

        The handler type is automatically extracted from the handler instance
        using type(handler).

        Args:
            handler: A handler instance to register. The handler class will be
                extracted and used as the key for resolution.

        Examples:
            ```python
            resolver = SimpleResolver()

            # Register handlers
            resolver.register(CreateUserHandler())
            resolver.register(UpdateUserHandler())
            ```

        Note:
            The handler parameter should be an *instance*, not a class. If you
            need lazy instantiation, consider using DependencyInjectorResolver.
        """
        handler_class = type(handler)
        self._handlers[handler_class] = handler

    def resolve(self, handler_class: type["Handler[Any]"]) -> "Handler[Any]":
        """Resolve and return a handler instance for the given handler type.

        This is the main resolution method called by the Mediator to obtain
        a handler instance for processing a request.

        Args:
            handler_class: The handler class to resolve.

        Returns:
            The handler instance that was registered for this handler type.

        Raises:
            HandlerNotFoundError: If no handler is registered for the handler type.
                The error message includes a list of available handlers to help
                with debugging.

        Examples:
            ```python
            resolver.register(CreateUserHandler())

            # Later (called by mediator)...
            handler = resolver.resolve(CreateUserHandler)
            response = handler(CreateUserRequest(username="alice"))
            ```

        Note:
            This method returns the same handler instance that was registered.
            For new instances on each resolution, use DependencyInjectorResolver
            with Factory providers.
        """
        if handler_class not in self._handlers:
            available = list(self._handlers.keys())
            raise errors.HandlerNotFoundError(handler_class, available)
        return self._handlers[handler_class]
