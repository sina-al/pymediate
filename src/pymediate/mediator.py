"""Asynchronous mediator implementation for routing requests to handlers."""

import asyncio

from ._internal.mediator import MediatorMixin
from ._internal.pipeline import compose_async
from .event import Event
from .pipeline import PipelineBehavior
from .request import Request


class Mediator(MediatorMixin):
    """Routes requests to their async handlers using a service provider.

    The mediator receives a request, looks up its handler type from the registry
    (populated automatically when `RequestHandler[RequestT]` subclasses are
    defined), resolves a handler instance from the service provider, and awaits
    it - `send()` is a coroutine, built to work with `RequestHandler`'s
    `async def __call__`.

    `send()` infers its return type from the request's `Request[ResponseT]` type
    parameter, so the response is fully typed at the call site with no casts needed.

    Examples:
        Basic usage with Services:
            ```python
            import asyncio
            from dataclasses import dataclass
            from pymediate import Mediator, Request, RequestHandler, Services

            @dataclass
            class UserResponse:
                user_id: int
                username: str

            @dataclass
            class CreateUserRequest(Request[UserResponse]):
                username: str

            class CreateUserHandler(RequestHandler[CreateUserRequest]):
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
        For a synchronous mediator, use `pymediate.sync.Mediator` instead.

    See Also:
        - Services: Build a ServiceProvider by hand.
        - DependencyInjectorServiceProvider: Build one from a DI container instead.
        - RequestHandler: Async handler base class.
        - pymediate.sync.Mediator: Sync mediator variant.
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
                from pymediate import PipelineBehavior, Request

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
              To run one without a mediator, call it directly:
              `await behavior(request, lambda: handler(request))`.
            - pymediate.sync.Mediator: Sync mediator variant.
        """
        handler = self._resolve_handler(request)
        behaviors = self._resolve_behaviors(request, PipelineBehavior)

        # Fast path: no applicable behaviors means no chain construction at all.
        if not behaviors:
            return await handler(request)  # type: ignore[no-any-return]
        return await compose_async(behaviors, handler)(request)  # type: ignore[no-any-return]

    async def publish(self, event: Event) -> None:
        """Publish an event to every async handler subscribed to its type.

        Resolves every `EventHandler` registered for the event's exact class
        (populated automatically when `EventHandler[EventT]` subclasses are
        defined) and runs all of them **concurrently** via `asyncio.gather`
        (tasks are created in registration order, then awaited together).
        Publishing with zero subscribers is a no-op, not an error.

        All handler instances are resolved before any handler runs, so a
        missing registration fails immediately and never causes partial
        delivery. If handlers raise during execution, the remaining handlers
        still run to completion, and the failures are re-raised together as an
        `ExceptionGroup` once all handlers have finished.

        Args:
            event: The event instance to publish.

        Raises:
            ServiceNotFoundError: If a subscribed handler class has no
                registered instance in the service provider.
            ExceptionGroup: If one or more handlers raised; contains every
                exception. Handle selectively with `except*`.

        Examples:
            Publishing to multiple async subscribers:
                ```python
                import asyncio
                from dataclasses import dataclass
                from pymediate import Event, EventHandler, Mediator, Services

                @dataclass
                class OrderPlaced(Event):
                    order_id: int

                class SendConfirmation(EventHandler[OrderPlaced]):
                    async def __call__(self, event: OrderPlaced) -> None:
                        print(f"confirming order {event.order_id}")

                class UpdateAnalytics(EventHandler[OrderPlaced]):
                    async def __call__(self, event: OrderPlaced) -> None:
                        print(f"recording order {event.order_id}")

                async def main():
                    services = Services()
                    services.add(SendConfirmation()).add(UpdateAnalytics())
                    mediator = Mediator(services.provider())

                    await mediator.publish(OrderPlaced(order_id=42))

                asyncio.run(main())
                ```

        Note:
            Handlers for one publish run concurrently - they must not rely on
            each other's effects or mutate shared state without
            synchronization. Publishing dispatches on the exact class of the
            event instance, and pipeline behaviors wrap `send()` only; they do
            not run on publishes.

        See Also:
            - Event: Base class for publishable events.
            - EventHandler: Base class for async subscribers.
            - pymediate.sync.Mediator.publish: Sync variant; runs handlers
              sequentially in registration order.
        """
        handlers = self._resolve_event_handlers(event)
        if not handlers:
            return

        results = await asyncio.gather(
            *(handler(event) for handler in handlers), return_exceptions=True
        )
        exceptions = [result for result in results if isinstance(result, BaseException)]

        if exceptions:
            raise BaseExceptionGroup(
                f"{len(exceptions)} of {len(handlers)} event handlers raised while "
                f"publishing {type(event).__name__}",
                exceptions,
            )
