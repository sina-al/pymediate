"""Mediator implementation for routing requests to handlers."""

from collections.abc import Iterator

from .._internal.mediator import MediatorMixin
from .._internal.pipeline import compose
from ..event import Event
from ..request import Request
from ..stream import StreamRequest
from .pipeline import PipelineBehavior


class Mediator(MediatorMixin):
    """Routes requests to their handlers using a service provider.

    The mediator receives a request, looks up its handler type from the registry
    (populated automatically when `RequestHandler[RequestT]` subclasses are defined),
    resolves a handler instance from the service provider, and invokes it.

    `send()` infers its return type from the request's `Request[ResponseT]` type
    parameter, so the response is fully typed at the call site with no casts needed.

    Examples:
        Basic usage with Services:
            ```python
            from pymediate.sync import Mediator, Services

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
        For an async mediator, use `pymediate.Mediator` instead.

    See Also:
        - Services: Build a ServiceProvider by hand.
        - DependencyInjectorServiceProvider: Build one from a DI container instead.
        - pymediate.Mediator: Async mediator variant.
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
                from pymediate.sync import PipelineBehavior, Request

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
              To run one without a mediator, call it directly:
              `behavior(request, lambda: handler(request))`.
        """
        handler = self._resolve_handler(request)
        behaviors = self._resolve_behaviors(request, PipelineBehavior)

        # Fast path: no applicable behaviors means no chain construction at all.
        if not behaviors:
            return handler(request)  # type: ignore[no-any-return]
        return compose(behaviors, handler)(request)  # type: ignore[no-any-return]

    def stream[ChunkT](self, request: StreamRequest[ChunkT]) -> Iterator[ChunkT]:
        """Route a stream request to its handler and return the chunk stream.

        Resolves the `StreamRequestHandler` registered for the request's type and
        returns its generator. The handler is resolved **eagerly** - a missing
        registration raises `HandlerNotFoundError` here, at the `stream()` call, not on
        first iteration - while the stream itself is **lazy**: the handler's body runs
        only as chunks are pulled with `for`.

        `stream()` infers its element type from the request's `StreamRequest[ChunkT]`
        type parameter, so each chunk is fully typed at the call site with no casts.

        Args:
            request: The stream request instance to dispatch.

        Returns:
            An iterator of chunks, typed as Iterator[ChunkT].

        Raises:
            HandlerNotFoundError: If no handler is registered for the request type.

        Examples:
            Streaming tokens from a completion request:
                ```python
                from collections.abc import Iterator
                from dataclasses import dataclass
                from pymediate.sync import (
                    Mediator, Services, StreamRequest, StreamRequestHandler
                )

                @dataclass
                class StreamCompletion(StreamRequest[str]):
                    prompt: str

                class CompletionHandler(StreamRequestHandler[StreamCompletion]):
                    def __call__(self, request: StreamCompletion) -> Iterator[str]:
                        yield from request.prompt.split()

                services = Services()
                services.add(CompletionHandler())
                mediator = Mediator(services.provider())

                for token in mediator.stream(StreamCompletion(prompt="hi there")):
                    print(token)  # token is typed as str
                ```

        Note:
            Pipeline behaviors wrap `send()` only; they do not run on `stream()`.

        See Also:
            - StreamRequest: Base class for streaming requests.
            - StreamRequestHandler: Base class for stream handlers (sync version).
            - pymediate.Mediator.stream: Async variant returning an AsyncIterator.
        """
        handler = self._resolve_handler(request)
        return handler(request)  # type: ignore[no-any-return]

    def publish(self, event: Event) -> None:
        """Publish an event to every handler subscribed to its type.

        Resolves every `EventHandler` registered for the event's exact class
        (populated automatically when `EventHandler[EventT]` subclasses are
        defined) and invokes each one with the event, in registration order.
        Publishing with zero subscribers is a no-op, not an error.

        All handler instances are resolved before any handler runs, so a
        missing registration fails immediately and never causes partial
        delivery. If handlers raise during execution, the remaining handlers
        still run, and the failures are re-raised together as an
        `ExceptionGroup` once all handlers have finished.

        Args:
            event: The event instance to publish.

        Raises:
            ServiceNotFoundError: If a subscribed handler class has no
                registered instance in the service provider.
            ExceptionGroup: If one or more handlers raised; contains every
                exception. Handle selectively with `except*`.

        Examples:
            Publishing to multiple subscribers:
                ```python
                from dataclasses import dataclass
                from pymediate.sync import Event, EventHandler, Mediator, Services

                @dataclass
                class OrderPlaced(Event):
                    order_id: int

                class SendConfirmation(EventHandler[OrderPlaced]):
                    def __call__(self, event: OrderPlaced) -> None:
                        print(f"confirming order {event.order_id}")

                class UpdateAnalytics(EventHandler[OrderPlaced]):
                    def __call__(self, event: OrderPlaced) -> None:
                        print(f"recording order {event.order_id}")

                services = Services()
                services.add(SendConfirmation()).add(UpdateAnalytics())
                mediator = Mediator(services.provider())

                mediator.publish(OrderPlaced(order_id=42))
                # confirming order 42
                # recording order 42
                ```

            Handling subscriber failures selectively:
                ```python
                try:
                    mediator.publish(OrderPlaced(order_id=42))
                except* ConnectionError as group:
                    for exc in group.exceptions:
                        print(f"subscriber unavailable: {exc}")
                ```

        Note:
            Publishing dispatches on the exact class of the event instance -
            handlers subscribed to a base event class do not receive derived
            events. Pipeline behaviors wrap `send()` only; they do not run on
            publishes.

        See Also:
            - Event: Base class for publishable events.
            - EventHandler: Base class for subscribers (sync version).
            - pymediate.Mediator.publish: Async variant; runs handlers
              concurrently.
        """
        handlers = self._resolve_event_handlers(event)
        if not handlers:
            return

        exceptions: list[Exception] = []
        for handler in handlers:
            try:
                handler(event)
            except Exception as exc:
                exceptions.append(exc)

        if exceptions:
            raise ExceptionGroup(
                f"{len(exceptions)} of {len(handlers)} event handlers raised while "
                f"publishing {type(event).__name__}",
                exceptions,
            )
