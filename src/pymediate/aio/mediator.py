"""Asynchronous mediator implementation for routing requests to handlers."""

from .._internal.mediator import MediatorMixin
from ..request import Request
from .pipeline import Pipeline, PipelineBehavior


class Mediator(MediatorMixin):
    """Routes requests to their async handlers using a service provider.

    The async mirror of `pymediate.Mediator`: it works the same way, but `send()`
    is a coroutine that awaits the resolved handler, so it's built to work with
    `pymediate.aio.Handler` subclasses.

    `send()` infers its return type from the request's `Request[ResponseT]` type
    parameter, so the response is fully typed at the call site with no casts needed.

    Examples:
        Basic usage with Services:
            ```python
            import asyncio
            from dataclasses import dataclass
            from pymediate import Request, Services
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
                    await asyncio.sleep(0.1)  # Simulate an async database call
                    return UserResponse(user_id=1, username=request.username)

            async def main():
                services = Services()
                services.add(CreateUserHandler())
                mediator = Mediator(services.provider())

                response = await mediator.send(CreateUserRequest(username="alice"))
                # response is correctly typed as UserResponse
                print(response.user_id)

            asyncio.run(main())
            ```

        Usage with dependency injection:
            ```python
            from pymediate.providers import DependencyInjectorServiceProvider

            async def main():
                container = AppContainer()
                provider = DependencyInjectorServiceProvider(container)
                mediator = Mediator(provider)

                response = await mediator.send(CreateUserRequest(username="alice"))
            ```

    Note:
        For a synchronous mediator, use `pymediate.Mediator` instead.

    See Also:
        - Services: Build a ServiceProvider by hand.
        - DependencyInjectorServiceProvider: Build one from a DI container instead.
        - pymediate.Mediator: Sync mediator variant.
        - pymediate.aio.Handler: Async handler base class.
    """

    async def send[ResponseT](self, request: Request[ResponseT]) -> ResponseT:
        """Send a request and await the typed response from its handler.

        Resolves the handler registered for the request's type, discovers any
        registered async `PipelineBehavior` instances that apply to this request,
        and awaits the handler - wrapped by those behaviors, if any - returning its
        response.

        Args:
            request: The request instance to send.

        Returns:
            The response from the handler, typed as ResponseT.

        Raises:
            HandlerNotFoundError: If no handler is registered for the request type.

        Examples:
            Basic usage, no behaviors:
                ```python
                @dataclass
                class CreateUserRequest(Request[UserCreatedResponse]):
                    username: str

                services = Services()
                services.add(AsyncCreateUserHandler())
                mediator = Mediator(services.provider())

                response = await mediator.send(CreateUserRequest(username="alice"))
                # response is typed as UserCreatedResponse
                ```

            With pipeline behaviors:
                ```python
                from pymediate import Request
                from pymediate.aio import PipelineBehavior

                class AsyncLoggingBehavior(PipelineBehavior[Request]):
                    async def __call__(self, request, next):
                        print(f"Before: {type(request).__name__}")
                        response = await next()
                        print(f"After: {type(request).__name__}")
                        return response

                services = Services()
                services.add(AsyncLoggingBehavior())      # Registered first = outermost
                services.add(AsyncCreateUserHandler())
                mediator = Mediator(services.provider())

                response = await mediator.send(CreateUserRequest(username="alice"))
                ```

        Note:
            If no behaviors apply to a request, the handler is awaited directly -
            there's no pipeline-construction overhead. Otherwise, one is built per
            request from every applicable behavior, in registration order (first
            registered is outermost), then the request's handler. Every behavior in
            the pipeline must itself be async (`async def __call__`).

        See Also:
            - PipelineBehavior: Base class for behaviors auto-discovered by send().
            - Pipeline: Compose behaviors and a handler manually, without a mediator.
            - pymediate.Mediator: Sync mediator variant.
        """
        handler = self._resolve_handler(request)
        behaviors = self._resolve_behaviors(request, PipelineBehavior)

        # Fast path: no applicable behaviors means no pipeline construction at all.
        if not behaviors:
            return await handler(request)  # type: ignore[no-any-return]
        return await Pipeline(behaviors, handler)(request)
