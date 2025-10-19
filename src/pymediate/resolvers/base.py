"""Base resolver protocol for PyMediate."""

from typing import TYPE_CHECKING, Protocol, TypeVar

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
