"""Mediator implementation for routing requests to handlers."""

from ._internal import registry
from ._internal.mediator import MediatorBaseMixin
from .request import Request


class Mediator(MediatorBaseMixin):
    """Mediator that routes requests to their handlers using a resolver.

    The mediator is the central coordination point in the mediator pattern.
    It receives requests, looks up the appropriate handler type from the registry,
    uses a resolver to obtain a handler instance, then delegates the actual
    processing to that handler.

    The mediator provides type-safe request routing with automatic response
    type inference. When you call send() with a Request[ResponseT], the return
    type is automatically inferred as ResponseT by the type checker.

    Attributes:
        _resolver: The resolver instance used to obtain handler instances.

    Examples:
        Basic usage with SimpleResolver:
            ```python
            resolver = SimpleResolver()
            resolver.register(CreateUserHandler())

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
        The mediator looks up handler types from the registry (which maps
        request types to handler types), then uses the resolver to instantiate
        the handler. This separation of concerns means the resolver only needs
        to know about handler instantiation, not request-to-handler mapping.

        For asynchronous mediator, use `pymediate.aio.Mediator` instead.

    See Also:
        - Resolver: Protocol for resolving handler instances
        - SimpleResolver: Dict-based resolver implementation
        - DependencyInjectorResolver: DI container-based resolver
        - pymediate.aio.Mediator: Async mediator variant
    """

    def send[ResponseT](self, request: Request[ResponseT]) -> ResponseT:
        """Send a request and get the typed response from its handler.

        This is the main entry point for the mediator pattern. It takes a request,
        looks up the handler type from the registry, resolves the handler instance,
        invokes it, and returns the response.

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
        from . import errors

        request_type = type(request)
        handler_class = registry.get_handler_class(request_type)
        if handler_class is None:
            raise errors.HandlerNotFoundError(request_type, [])
        handler = self._resolver.resolve(handler_class)
        return handler(request)  # type: ignore[no-any-return]
