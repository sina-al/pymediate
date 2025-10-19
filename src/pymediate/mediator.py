"""Mediator implementation for routing requests to handlers."""

from pymediate.request import Request
from pymediate.resolver import Resolver


class Mediator:
    """Mediator that routes requests to their handlers using a resolver.

    The mediator is the central coordination point in the mediator pattern.
    It receives requests and uses a resolver to obtain the appropriate handler
    instance, then delegates the actual processing to that handler.

    The mediator provides type-safe request routing with automatic response
    type inference. When you call send() with a Request[ResponseT], the return
    type is automatically inferred as ResponseT by the type checker.

    Attributes:
        _resolver: The resolver instance used to obtain handler instances.

    Examples:
        Basic usage with SimpleResolver:
            ```python
            resolver = SimpleResolver()
            resolver.register(CreateUserRequest, CreateUserHandler())

            mediator = Mediator(resolver)
            response = mediator.send(CreateUserRequest(username="alice"))
            # response is correctly typed as UserCreatedResponse
            ```

        Usage with dependency injection:
            ```python
            container = AppContainer()
            resolver = DependencyInjectorResolver(container)
            mediator = Mediator(resolver)

            response = mediator.send(CreateUserRequest(username="alice"))
            ```

    Note:
        The mediator doesn't know anything about specific handlers or requests.
        It's completely generic and relies on the resolver to provide the
        correct handler instances.

    See Also:
        - Resolver: Protocol for resolving handler instances
        - SimpleResolver: Dict-based resolver implementation
        - DependencyInjectorResolver: DI container-based resolver
    """

    def __init__(self, resolver: Resolver) -> None:
        """Initialize mediator with a resolver for obtaining handler instances.

        Args:
            resolver: Any object implementing the Resolver protocol. This can be
                a SimpleResolver, DependencyInjectorResolver, or your own custom
                resolver implementation.

        Examples:
            ```python
            resolver = SimpleResolver()
            mediator = Mediator(resolver)
            ```
        """
        self._resolver = resolver

    def send[ResponseT](self, request: Request[ResponseT]) -> ResponseT:
        """Send a request and get the typed response from its handler.

        This is the main entry point for the mediator pattern. It takes a request,
        resolves the appropriate handler, invokes it, and returns the response.

        The response type is automatically inferred from the request's type parameter,
        providing full type safety from request to response.

        Args:
            request: The request instance to send. Must be a subclass of Request[ResponseT].

        Returns:
            The response from the handler, with type ResponseT matching the request's
            type parameter.

        Raises:
            HandlerNotFoundError: If no handler is registered for the request type.
            DIContainerError: If using DI and the container fails to provide a handler.

        Examples:
            ```python
            # Define request and response
            @dataclass
            class CreateUserRequest(Request[UserCreatedResponse]):
                username: str

            # Send request
            response = mediator.send(CreateUserRequest(username="alice"))
            # response is typed as UserCreatedResponse

            # Type checker knows the return type
            print(response.user_id)  # Valid
            print(response.username)  # Valid
            ```

        Type Parameters:
            ResponseT: The response type, inferred from Request[ResponseT].
        """
        request_type = type(request)
        handler = self._resolver.resolve(request_type)
        return handler(request)  # type: ignore[no-any-return]
