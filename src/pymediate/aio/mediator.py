"""Asynchronous mediator implementation for routing requests to handlers."""

from .._internal.mediator import MediatorBaseMixin
from ..request import Request


class Mediator(MediatorBaseMixin):
    """Asynchronous mediator that routes requests to their handlers using a resolver.

    The mediator is the central coordination point in the mediator pattern.
    It receives requests and uses a resolver to obtain the appropriate handler
    instance, then delegates the actual processing to that handler.

    This async variant is designed to work with async handlers (pymediate.aio.Handler).
    The send() method is async and will await the handler's execution.

    The mediator provides type-safe request routing with automatic response
    type inference. When you call send() with a Request[ResponseT], the return
    type is automatically inferred as ResponseT by the type checker.

    Attributes:
        _resolver: The resolver instance used to obtain handler instances.

    Examples:
        Basic usage with SimpleResolver:
            ```python
            import asyncio
            from pymediate import Request, SimpleResolver
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
                resolver = SimpleResolver()
                resolver.register(CreateUserRequest, CreateUserHandler())

                mediator = Mediator(resolver)
                response = await mediator.send(CreateUserRequest(username="alice"))
                # response is correctly typed as UserResponse
                print(response.user_id)

            asyncio.run(main())
            ```

        Usage with dependency injection:
            ```python
            async def main():
                container = AppContainer()
                resolver = DependencyInjectorResolver(container)
                mediator = Mediator(resolver)

                response = await mediator.send(CreateUserRequest(username="alice"))
            ```

    Note:
        The mediator doesn't know anything about specific handlers or requests.
        It's completely generic and relies on the resolver to provide the
        correct handler instances.

        For synchronous mediator, use `pymediate.Mediator` instead.

    See Also:
        - Resolver: Protocol for resolving handler instances
        - SimpleResolver: Dict-based resolver implementation
        - DependencyInjectorResolver: DI container-based resolver
        - pymediate.Mediator: Sync mediator variant
        - pymediate.aio.Handler: Async handler variant
    """

    async def send[ResponseT](self, request: Request[ResponseT]) -> ResponseT:
        """Send a request asynchronously and get the typed response from its handler.

        This is the main entry point for the async mediator pattern. It takes a request,
        resolves the appropriate handler, invokes it asynchronously, and returns the response.

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
        request_type = type(request)
        handler = self._resolver.resolve(request_type)
        return await handler(request)  # type: ignore[no-any-return]
