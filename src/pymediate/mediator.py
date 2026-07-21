"""Asynchronous mediator implementation for routing requests to handlers."""

import asyncio
from collections.abc import AsyncIterator, Sequence
from typing import Any

from ._internal.mediator import MediatorMixin
from ._internal.pipeline import compose_async
from .notification import Notification
from .pipeline import PipelineBehavior
from .request import Request
from .service import ServiceProvider
from .stream import StreamRequest


class Mediator(MediatorMixin):
    """Routes requests to their async handlers using a service provider.

    ``send()`` returns one typed response, ``stream()`` returns an asynchronous
    iterator of typed chunks, and ``publish()`` notifies every handler subscribed
    to a notification's exact type. The mediator uses a ``ServiceProvider`` to resolve
    handler and pipeline-behavior instances, and the ``behaviors`` sequence
    passed at construction to determine which behaviors run and in what order.

    Static type checkers infer the result of ``send()`` from
    ``Request[ResponseT]`` and the chunks from ``StreamRequest[ChunkT]``.

    Examples:
        Sending a request with ``Services``:
            ```python
            import asyncio
            from dataclasses import dataclass

            from pymediate import Mediator, Request, RequestHandler, Services

            @dataclass(frozen=True)
            class OrderReceipt:
                order_id: int
                summary: str

            @dataclass(frozen=True)
            class PlaceOrder(Request[OrderReceipt]):
                customer_id: int
                item: str
                quantity: int

            class PlaceOrderHandler(RequestHandler[PlaceOrder]):
                async def __call__(self, request: PlaceOrder) -> OrderReceipt:
                    return OrderReceipt(
                        order_id=42,
                        summary=f"{request.quantity} × {request.item}",
                    )

            async def main() -> None:
                services = Services().add(PlaceOrderHandler())
                mediator = Mediator(services=services.provider())

                receipt = await mediator.send(
                    PlaceOrder(customer_id=7, item="tea", quantity=2),
                )
                print(receipt.order_id)

            asyncio.run(main())
            ```

    Note:
        Use ``pymediate.sync.Mediator`` for synchronous dispatch.
    """

    def __init__(
        self,
        services: ServiceProvider,
        *,
        behaviors: Sequence[type[PipelineBehavior[Any]]] | None = None,
    ) -> None:
        """Initialize the mediator with a service provider and its pipeline.

        The ``behaviors`` sequence declares the pipeline: which behavior classes
        wrap ``send()`` and in what order, the first entry outermost. Behaviors
        registered with the provider but not listed are not part of this
        mediator's pipeline. The sequence is validated here, eagerly, so a
        misdeclared pipeline fails at construction rather than at a dispatch.

        Args:
            services: An object implementing ``ServiceProvider``. The keyword
                name is ``services``.
            behaviors: Ordered asynchronous ``PipelineBehavior`` subclasses
                declaring the pipeline. Omitted or None means no behaviors run.

        Raises:
            InvalidPipelineBehaviorsError: If a ``behaviors`` entry is not an
                asynchronous ``PipelineBehavior`` subclass, is not registered
                with the provider, or is listed more than once.

        Note:
            The mediator retains this provider for later dispatches. Handler and
            behavior lifetimes therefore follow the provider's policy.
        """
        super().__init__(services, behaviors, PipelineBehavior)

    async def send[ResponseT](self, request: Request[ResponseT]) -> ResponseT:
        """Send a request and await the typed response from its handler.

        The mediator finds the handler class registered for the request's exact
        type, resolves its instance, and awaits it. Behaviors from the
        construction-time ``behaviors`` sequence whose ``should_apply()`` accepts
        the request wrap that call, in sequence order - the first listed
        applicable behavior is the outermost.

        Args:
            request: The request instance to send.

        Returns:
            The response from the handler, typed as ResponseT.

        Raises:
            HandlerNotFoundError: If no handler is registered for the request type.
            ServiceNotFoundError: If the service provider cannot resolve the handler
                or an applicable behavior.

        Note:
            If no behavior applies, the handler is awaited directly and no behavior
            chain is constructed. Handler and behavior exceptions propagate unchanged.
        """
        handler = self._resolve_handler(request)
        behaviors = self._resolve_behaviors(request)

        # Fast path: no applicable behaviors means no chain construction at all.
        if not behaviors:
            return await handler(request)  # type: ignore[no-any-return]
        return await compose_async(behaviors, handler)(request)  # type: ignore[no-any-return]

    def stream[ChunkT](self, request: StreamRequest[ChunkT]) -> AsyncIterator[ChunkT]:
        """Route a stream request to its handler and return the async chunk stream.

        The mediator finds the ``StreamRequestHandler`` registered for the request's
        exact type and resolves its instance at the ``stream()`` call. The async
        generator body remains lazy and runs as the caller consumes chunks.

        Args:
            request: The stream request instance to dispatch.

        Returns:
            An async iterator of chunks, typed as AsyncIterator[ChunkT].

        Raises:
            HandlerNotFoundError: If no handler is registered for the request type.
            ServiceNotFoundError: If the service provider cannot resolve the handler.

        Note:
            Do not await ``stream()`` itself; iterate its result with ``async for``.
            Pipeline behaviors do not wrap streams. Exceptions from the generator
            body propagate during iteration.
        """
        handler = self._resolve_handler(request)
        return handler(request)  # type: ignore[no-any-return]

    async def publish(self, notification: Notification) -> None:
        """Publish a notification to every async handler subscribed to its type.

        The mediator resolves every ``NotificationHandler`` registered for the notification's
        exact class before invoking any of them. It then runs the handlers
        concurrently. Publishing with no subscribers returns without error.

        Ordinary ``Exception`` failures are collected after all handlers finish
        and raised together as an ``ExceptionGroup``. Other collected
        ``BaseException`` values produce a ``BaseExceptionGroup``. Python treats
        ``KeyboardInterrupt`` and ``SystemExit`` specially: they propagate instead
        of being grouped and can cancel unfinished sibling handlers.

        Args:
            notification: The notification instance to publish.

        Raises:
            ServiceNotFoundError: If a subscribed handler class has no
                registered instance in the service provider.
            ExceptionGroup: If one or more handlers raise an ``Exception``.
            BaseExceptionGroup: If the collected failures include another
                ``BaseException`` type.
            KeyboardInterrupt: If a handler raises ``KeyboardInterrupt``.
            SystemExit: If a handler raises ``SystemExit``.

        Note:
            Publishing dispatches on the notification's exact class. Pipeline behaviors
            do not wrap notification publication. Notification subscriptions are shared with
            the synchronous API, so every handler for this exact notification type must
            be asynchronous.
        """
        handlers = self._resolve_notification_handlers(notification)
        if not handlers:
            return

        results = await asyncio.gather(
            *(handler(notification) for handler in handlers), return_exceptions=True
        )
        exceptions = [result for result in results if isinstance(result, BaseException)]

        if exceptions:
            raise BaseExceptionGroup(
                f"{len(exceptions)} of {len(handlers)} notification handlers raised while "
                f"publishing {type(notification).__name__}",
                exceptions,
            )
