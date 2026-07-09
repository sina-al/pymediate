"""Mediator implementation for routing requests to handlers."""

from ._internal.mediator import MediatorMixin
from .pipeline import Pipeline, PipelineBehavior
from .request import Request


class Mediator(MediatorMixin):
    """Routes requests to their handlers using a service provider.

    The mediator receives a request, looks up its handler type from the registry
    (populated automatically when `Handler[RequestT]` subclasses are defined),
    resolves a handler instance from the service provider, and invokes it.

    `send()` infers its return type from the request's `Request[ResponseT]` type
    parameter, so the response is fully typed at the call site with no casts needed.

    Examples:
        Basic usage with Services:
            ```python
            from pymediate import Mediator, Services

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
        For an async mediator, use `pymediate.aio.Mediator` instead.

    See Also:
        - Services: Build a ServiceProvider by hand.
        - DependencyInjectorServiceProvider: Build one from a DI container instead.
        - pymediate.aio.Mediator: Async mediator variant.
    """

    def send[ResponseT](self, request: Request[ResponseT]) -> ResponseT:
        """Send a request and get the typed response from its handler.

        Resolves the handler registered for the request's type, discovers any
        registered `PipelineBehavior` instances that apply to this request, and
        invokes the handler - wrapped by those behaviors, if any - returning its
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
                services.add(CreateUserHandler())
                mediator = Mediator(services.provider())

                response = mediator.send(CreateUserRequest(username="alice"))
                # response is typed as UserCreatedResponse
                ```

            With pipeline behaviors:
                ```python
                from pymediate import PipelineBehavior, Request

                class LoggingBehavior(PipelineBehavior[Request]):
                    def __call__(self, request, next):
                        print(f"Before: {type(request).__name__}")
                        response = next()
                        print(f"After: {type(request).__name__}")
                        return response

                services = Services()
                services.add(LoggingBehavior())     # Registered first = outermost
                services.add(CreateUserHandler())
                mediator = Mediator(services.provider())

                response = mediator.send(CreateUserRequest(username="alice"))
                # Output:
                # Before: CreateUserRequest
                # After: CreateUserRequest
                ```

        Note:
            If no behaviors apply to a request, the handler is called directly -
            there's no pipeline-construction overhead. Otherwise, one is built per
            request from every applicable behavior, in registration order (first
            registered is outermost), then the request's handler.

        See Also:
            - PipelineBehavior: Base class for behaviors auto-discovered by send().
            - Pipeline: Compose behaviors and a handler manually, without a mediator.
        """
        handler = self._resolve_handler(request)
        behaviors = self._resolve_behaviors(request, PipelineBehavior)

        # Fast path: no applicable behaviors means no pipeline construction at all.
        if not behaviors:
            return handler(request)  # type: ignore[no-any-return]
        return Pipeline(behaviors, handler)(request)
