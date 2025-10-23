"""Asynchronous mediator implementation for routing requests to handlers."""

from .._internal import registry
from .._internal.mediator import MediatorBaseMixin
from ..request import Request


class Mediator(MediatorBaseMixin):
    """Asynchronous mediator that routes requests to their handlers using a service provider.

    The mediator is the central coordination point in the mediator pattern.
    It receives requests, looks up the appropriate handler type from the registry,
    uses a service provider to obtain a handler instance, then delegates the actual
    processing to that handler.

    This async variant is designed to work with async handlers (pymediate.aio.Handler).
    The send() method is async and will await the handler's execution.

    The mediator provides type-safe request routing with automatic response
    type inference. When you call send() with a Request[ResponseT], the return
    type is automatically inferred as ResponseT by the type checker.

    Attributes:
        _service_provider: The service provider instance used to obtain handler instances.

    Examples:
        Basic usage with ServiceCollection:
            ```python
            import asyncio
            from pymediate import Request
            from pymediate.service import ServiceCollection
            from pymediate.aio import Handler, Mediator

            @dataclass
            class UserResponse:
                user_id: int
                username: str

            @dataclass
            class CreateUserRequest(Request[UserResponse]):
                username: str

            class CreateUserHandler(Handler[CreateUserRequest]):
                async def __call__(self, request: CreateUserRequest) -> UserResponse:
                    # Simulate async database operation
                    await asyncio.sleep(0.1)
                    return UserResponse(user_id=1, username=request.username)

            async def main():
                services = ServiceCollection()
                services.add(CreateUserHandler())
                provider = services.build_provider()

                mediator = Mediator(provider)
                response = await mediator.send(CreateUserRequest(username="alice"))
                # response is correctly typed as UserResponse
                print(response.user_id)

            asyncio.run(main())
            ```

        Usage with dependency injection:
            ```python
            from pymediate.service_providers import DependencyInjectorServiceProvider

            async def main():
                container = AppContainer()
                provider = DependencyInjectorServiceProvider(container)
                mediator = Mediator(provider)

                response = await mediator.send(CreateUserRequest(username="alice"))
            ```

    Note:
        The mediator looks up handler types from the registry (which maps
        request types to handler types), then uses the service provider to instantiate
        the handler. This separation of concerns means the service provider only needs
        to know about handler instantiation, not request-to-handler mapping.

        For synchronous mediator, use `pymediate.Mediator` instead.

    See Also:
        - ServiceProvider: Protocol for resolving service instances
        - ServiceCollection: Manual service registration
        - DependencyInjectorServiceProvider: DI container integration
        - pymediate.Mediator: Sync mediator variant
        - pymediate.aio.Handler: Async handler variant
    """

    async def send[ResponseT](self, request: Request[ResponseT]) -> ResponseT:
        """Send a request asynchronously and get the typed response from its handler.

        This is the main entry point for the async mediator pattern. It takes a request,
        looks up the handler type from the registry, resolves the handler instance,
        invokes it asynchronously, and returns the response.

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

            # Send request asynchronously
            response = await mediator.send(CreateUserRequest(username="alice"))
            # response is typed as UserCreatedResponse

            # Type checker knows the return type
            print(response.user_id)  # Valid
            print(response.username)  # Valid
            ```

        Type Parameters:
            ResponseT: The response type, inferred from Request[ResponseT].
        """
        from typing import Any

        from .. import errors

        request_type = type(request)
        handler_class = registry.get_handler_class(request_type)
        if handler_class is None:
            raise errors.HandlerNotFoundError(request_type, [])
        handler: Any = self._service_provider.resolve(handler_class)
        return await handler(request)  # type: ignore[no-any-return]
