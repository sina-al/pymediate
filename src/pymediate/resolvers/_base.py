"""Base resolver protocol for PyMediate."""

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from pymediate.handler import Handler


class Resolver(Protocol):
    """Protocol for resolving handler instances from handler types.

    This protocol defines the interface for handler instantiation, enabling
    integration with various dependency injection frameworks, service
    locators, or custom instantiation strategies.

    The resolver is responsible solely for instantiating handlers from their
    types. The mediator handles the mapping from request types to handler types
    via the registry.

    Any class implementing this protocol can be used with the Mediator,
    making PyMediate flexible and framework-agnostic.

    Examples:
        Custom resolver with dict-based lookup:
            ```python
            class MyResolver:
                def __init__(self):
                    self.handlers = {}

                def resolve(self, handler_class: type[Handler]) -> Handler:
                    return self.handlers[handler_class]
            ```

        DI container integration:
            ```python
            class DIResolver:
                def __init__(self, container):
                    self.container = container

                def resolve(self, handler_class: type[Handler]) -> Handler:
                    return self.container.resolve(handler_class)
            ```

    See Also:
        - SimpleResolver: Built-in dict-based implementation
        - DependencyInjectorResolver: Integration with dependency-injector library
    """

    def resolve(self, handler_class: type["Handler[Any]"]) -> "Handler[Any]":
        """Resolve and return a handler instance for the given handler type.

        Args:
            handler_class: The handler class to instantiate.

        Returns:
            A handler instance of the given handler type.

        Raises:
            HandlerNotFoundError: If no handler can be resolved for the handler type.
        """
        ...
