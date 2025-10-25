"""Asynchronous mediator implementation for routing requests to handlers."""

from collections.abc import Sequence
from typing import Any

from .._internal import registry
from .._internal.mediator import MediatorMixin
from ..request import Request
from .pipeline import Pipeline, PipelineBehavior


class Mediator(MediatorMixin):
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
        Basic usage with Services:
            ```python
            import asyncio
            from pymediate import Request
            from pymediate.service import Services
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
                services = Services()
                services.add(CreateUserHandler())
                provider = services.provider()

                mediator = Mediator(provider)
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
        The mediator looks up handler types from the registry (which maps
        request types to handler types), then uses the service provider to instantiate
        the handler. This separation of concerns means the service provider only needs
        to know about handler instantiation, not request-to-handler mapping.

        For synchronous mediator, use `pymediate.Mediator` instead.

    See Also:
        - ServiceProvider: Protocol for resolving service instances
        - Services: Manual service registration
        - DependencyInjectorServiceProvider: DI container integration
        - pymediate.Mediator: Sync mediator variant
        - pymediate.aio.Handler: Async handler variant
    """

    async def send[ResponseT](self, request: Request[ResponseT]) -> ResponseT:
        """Send a request asynchronously and get the typed response from its handler.

        This is the main entry point for the async mediator pattern. It takes a request,
        looks up the handler type from the registry, resolves the handler instance,
        automatically discovers and applies any registered async pipeline behaviors,
        invokes the handler (wrapped by behaviors if any) asynchronously, and returns
        the response.

        Pipeline behaviors are automatically discovered by resolving all services
        that inherit from PipelineBehavior. Behaviors are applied in registration
        order, with the first registered behavior being the outermost wrapper.

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
            Basic usage without behaviors:
                ```python
                @dataclass
                class CreateUserRequest(Request[UserCreatedResponse]):
                    username: str

                # Register handler only
                services = Services()
                services.add(AsyncCreateUserHandler())
                mediator = Mediator(services.provider())

                # Send request
                response = await mediator.send(CreateUserRequest(username="alice"))
                # response is typed as UserCreatedResponse
                ```

            Automatic async behavior application:
                ```python
                from pymediate.aio.pipeline import PipelineBehavior

                class AsyncLoggingBehavior(PipelineBehavior):
                    async def __call__(self, request, next):
                        await log_to_db(f"Before: {type(request).__name__}")
                        response = await next()
                        await log_to_db(f"After: {type(request).__name__}")
                        return response

                # Register behaviors and handler
                services = Services()
                services.add(AsyncLoggingBehavior())      # Registered first = outermost
                services.add(AsyncValidationBehavior())   # Registered second
                services.add(AsyncCreateUserHandler())

                mediator = Mediator(services.provider())

                # Send request - behaviors automatically wrap handler
                response = await mediator.send(CreateUserRequest(username="alice"))
                ```

            With DI container (respects scopes):
                ```python
                from dependency_injector import containers, providers

                class Container(containers.DeclarativeContainer):
                    # Transient = new instance per request
                    logging = providers.Transient(AsyncLoggingBehavior)
                    # Singleton = shared instance
                    cache = providers.Singleton(AsyncCacheBehavior, ttl=300)
                    # Handler
                    create_user = providers.Factory(AsyncCreateUserHandler, db=...)

                provider = DependencyInjectorServiceProvider(container)
                mediator = Mediator(provider)

                # Behaviors resolved per request, respecting their scopes
                response = await mediator.send(CreateUserRequest(username="alice"))
                ```

        Performance Notes:
            - If no behaviors are registered, the handler is called directly (zero overhead)
            - Behaviors are resolved per request, respecting DI container scopes
            - The async pipeline is constructed once per request, then executed
            - All behaviors must be async (use async def __call__)

        Type Parameters:
            ResponseT: The response type, inferred from Request[ResponseT].

        See Also:
            - PipelineBehavior: Base class for auto-discovered async behaviors
            - Pipeline: Manual async pipeline construction
            - ServiceProvider.resolve_all(): How behaviors are discovered
            - pymediate.Mediator: Sync mediator variant
        """
        from .. import errors

        # Look up handler type from registry
        request_type = type(request)
        handler_class = registry.get_handler_class(request_type)
        if handler_class is None:
            raise errors.HandlerNotFoundError(request_type, [])

        # Resolve handler instance
        handler: Any = self._service_provider.resolve(handler_class)

        # Resolve all registered pipeline behaviors
        all_behaviors: Sequence[Any] = self._service_provider.resolve_all(PipelineBehavior)

        # Filter behaviors to only those that apply to this request
        applicable_behaviors = [
            behavior for behavior in all_behaviors
            if type(behavior).should_apply(request)
        ]

        # Fast path: if no applicable behaviors, call handler directly (zero overhead)
        if not applicable_behaviors:
            return await handler(request)  # type: ignore[no-any-return]

        # Construct and execute async pipeline with applicable behaviors
        pipeline: Pipeline[Any, ResponseT] = Pipeline(applicable_behaviors, handler)
        return await pipeline(request)
