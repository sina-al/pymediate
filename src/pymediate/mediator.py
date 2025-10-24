"""Mediator implementation for routing requests to handlers."""

from collections.abc import Sequence
from typing import Any

from ._internal import registry
from ._internal.mediator import MediatorMixin
from .pipeline import Pipeline, PipelineBehaviorBase
from .request import Request


class Mediator(MediatorMixin):
    """Mediator that routes requests to their handlers using a service provider.

    The mediator is the central coordination point in the mediator pattern.
    It receives requests, looks up the appropriate handler type from the registry,
    uses a service provider to obtain a handler instance, then delegates the actual
    processing to that handler.

    The mediator provides type-safe request routing with automatic response
    type inference. When you call send() with a Request[ResponseT], the return
    type is automatically inferred as ResponseT by the type checker.

    Attributes:
        _service_provider: The service provider instance used to obtain handler instances.

    Examples:
        Basic usage with Services:
            ```python
            from pymediate import Mediator
            from pymediate.service import Services

            services = Services()
            services.add(CreateUserHandler())
            provider = services.provider()

            mediator = Mediator(provider)
            response = mediator.send(CreateUserRequest(username="alice"))
            # response is correctly typed as UserCreatedResponse
            ```

        Usage with dependency injection:
            ```python
            from pymediate.providers import DependencyInjectorServiceProvider

            container = AppContainer()
            provider = DependencyInjectorServiceProvider(container)
            mediator = Mediator(provider)

            response = mediator.send(CreateUserRequest(username="alice"))
            ```

    Note:
        The mediator looks up handler types from the registry (which maps
        request types to handler types), then uses the service provider to instantiate
        the handler. This separation of concerns means the service provider only needs
        to know about handler instantiation, not request-to-handler mapping.

        For asynchronous mediator, use `pymediate.aio.Mediator` instead.

    See Also:
        - ServiceProvider: Protocol for resolving service instances
        - Services: Manual service registration
        - DependencyInjectorServiceProvider: DI container integration
        - pymediate.aio.Mediator: Async mediator variant
    """

    def send[ResponseT](self, request: Request[ResponseT]) -> ResponseT:
        """Send a request and get the typed response from its handler.

        This is the main entry point for the mediator pattern. It takes a request,
        looks up the handler type from the registry, resolves the handler instance,
        automatically discovers and applies any registered pipeline behaviors,
        invokes the handler (wrapped by behaviors if any), and returns the response.

        Pipeline behaviors are automatically discovered by resolving all services
        that inherit from PipelineBehaviorBase. Behaviors are applied in registration
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
                services.add(CreateUserHandler())
                mediator = Mediator(services.provider())

                # Send request
                response = mediator.send(CreateUserRequest(username="alice"))
                # response is typed as UserCreatedResponse
                ```

            Automatic behavior application:
                ```python
                from pymediate.pipeline import PipelineBehaviorBase

                class LoggingBehavior(PipelineBehaviorBase):
                    def __call__(self, request, next):
                        print(f"Before: {type(request).__name__}")
                        response = next()
                        print(f"After: {type(request).__name__}")
                        return response

                # Register behaviors and handler
                services = Services()
                services.add(LoggingBehavior())      # Registered first = outermost
                services.add(ValidationBehavior())   # Registered second
                services.add(CreateUserHandler())

                mediator = Mediator(services.provider())

                # Send request - behaviors automatically wrap handler
                response = mediator.send(CreateUserRequest(username="alice"))
                # Output:
                # Before: CreateUserRequest
                # After: CreateUserRequest
                ```

            With DI container (respects scopes):
                ```python
                from dependency_injector import containers, providers

                class Container(containers.DeclarativeContainer):
                    # Transient = new instance per request
                    logging = providers.Transient(LoggingBehavior)
                    # Singleton = shared instance
                    cache = providers.Singleton(CacheBehavior, ttl=300)
                    # Handler
                    create_user = providers.Factory(CreateUserHandler, db=...)

                provider = DependencyInjectorServiceProvider(container)
                mediator = Mediator(provider)

                # Behaviors resolved per request, respecting their scopes
                response = mediator.send(CreateUserRequest(username="alice"))
                ```

        Performance Notes:
            - If no behaviors are registered, the handler is called directly (zero overhead)
            - Behaviors are resolved per request, respecting DI container scopes
            - The pipeline is constructed once per request, then executed

        Type Parameters:
            ResponseT: The response type, inferred from Request[ResponseT].

        See Also:
            - PipelineBehaviorBase: Base class for auto-discovered behaviors
            - Pipeline: Manual pipeline construction
            - ServiceProvider.resolve_all(): How behaviors are discovered
        """
        from . import errors

        # Look up handler type from registry
        request_type = type(request)
        handler_class = registry.get_handler_class(request_type)
        if handler_class is None:
            raise errors.HandlerNotFoundError(request_type, [])

        # Resolve handler instance
        handler: Any = self._service_provider.resolve(handler_class)

        # Resolve all registered pipeline behaviors (if any)
        behaviors: Sequence[Any] = self._service_provider.resolve_all(PipelineBehaviorBase)

        # Fast path: if no behaviors, call handler directly (zero overhead)
        if not behaviors:
            return handler(request)  # type: ignore[no-any-return]

        # Construct and execute pipeline with behaviors
        pipeline: Pipeline[Any, ResponseT] = Pipeline(behaviors, handler)
        return pipeline(request)
