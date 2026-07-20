"""Mediator implementation for routing requests to handlers."""

from collections.abc import Iterator, Sequence
from typing import Any

from .._internal.mediator import MediatorMixin
from .._internal.pipeline import compose
from ..notification import Notification
from ..request import Request
from ..service import ServiceProvider
from ..stream import StreamRequest
from .pipeline import PipelineBehavior


class Mediator(MediatorMixin):
    """Routes requests to their handlers using a service provider.

    ``send()`` returns one typed response, ``stream()`` returns an iterator of
    typed chunks, and ``publish()`` notifies every handler subscribed to an
    notification's exact type. The mediator uses a ``ServiceProvider`` to resolve handler
    and pipeline-behavior instances, and the ``behaviors`` sequence passed at
    construction to determine which behaviors run and in what order.

    Static type checkers infer the result of ``send()`` from
    ``Request[ResponseT]`` and the chunks from ``StreamRequest[ChunkT]``.

    Examples:
        Sending a request with ``Services``:
            ```python
            from dataclasses import dataclass

            from pymediate.sync import Mediator, Request, RequestHandler, Services

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
                def __call__(self, request: PlaceOrder) -> OrderReceipt:
                    return OrderReceipt(
                        order_id=42,
                        summary=f"{request.quantity} × {request.item}",
                    )

            services = Services().add(PlaceOrderHandler())
            mediator = Mediator(services=services.provider())

            receipt = mediator.send(
                PlaceOrder(customer_id=7, item="tea", quantity=2),
            )
            print(receipt.order_id)
            ```

    Note:
        Use ``pymediate.Mediator`` for asynchronous dispatch.
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
            behaviors: Ordered synchronous ``PipelineBehavior`` subclasses
                declaring the pipeline. Omitted or None means no behaviors run.

        Raises:
            InvalidPipelineBehaviorsError: If a ``behaviors`` entry is not a
                synchronous ``PipelineBehavior`` subclass, is not registered
                with the provider, or is listed more than once.

        Note:
            The mediator retains this provider for later dispatches. Handler and
            behavior lifetimes therefore follow the provider's policy.
        """
        super().__init__(services, behaviors, PipelineBehavior)

    def send[ResponseT](self, request: Request[ResponseT]) -> ResponseT:
        """Send a request and get the typed response from its handler.

        The mediator finds the handler class registered for the request's exact
        type, resolves its instance, and calls it. Behaviors from the
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
            If no behavior applies, the handler is called directly and no behavior
            chain is constructed. Handler and behavior exceptions propagate unchanged.
        """
        handler = self._resolve_handler(request)
        behaviors = self._resolve_behaviors(request)

        # Fast path: no applicable behaviors means no chain construction at all.
        if not behaviors:
            return handler(request)  # type: ignore[no-any-return]
        return compose(behaviors, handler)(request)  # type: ignore[no-any-return]

    def stream[ChunkT](self, request: StreamRequest[ChunkT]) -> Iterator[ChunkT]:
        """Route a stream request to its handler and return the chunk stream.

        The mediator finds the ``StreamRequestHandler`` registered for the request's
        exact type and resolves its instance at the ``stream()`` call. The generator
        body remains lazy and runs as the caller consumes chunks.

        Args:
            request: The stream request instance to dispatch.

        Returns:
            An iterator of chunks, typed as Iterator[ChunkT].

        Raises:
            HandlerNotFoundError: If no handler is registered for the request type.
            ServiceNotFoundError: If the service provider cannot resolve the handler.

        Note:
            Pipeline behaviors do not wrap streams. Exceptions from the generator
            body propagate during iteration.
        """
        handler = self._resolve_handler(request)
        return handler(request)  # type: ignore[no-any-return]

    def publish(self, notification: Notification) -> None:
        """Publish a notification to every handler subscribed to its type.

        The mediator resolves every ``NotificationHandler`` registered for the notification's
        exact class before invoking any of them. It then runs the handlers
        sequentially in registration order. Publishing with no subscribers returns
        without error.

        If an ordinary ``Exception`` is raised, the remaining handlers still run.
        Their failures are raised together as an ``ExceptionGroup`` afterward.

        Args:
            notification: The notification instance to publish.

        Raises:
            ServiceNotFoundError: If a subscribed handler class has no
                registered instance in the service provider.
            ExceptionGroup: If one or more handlers raise an ``Exception``.

        Note:
            Publishing dispatches on the notification's exact class. Pipeline behaviors
            do not wrap notification publication. A ``BaseException`` that is not an
            ``Exception`` propagates immediately. Notification subscriptions are shared
            with the asynchronous API, so every handler for this exact notification type
            must be synchronous.
        """
        handlers = self._resolve_notification_handlers(notification)
        if not handlers:
            return

        exceptions: list[Exception] = []
        for handler in handlers:
            try:
                handler(notification)
            except Exception as exc:
                exceptions.append(exc)

        if exceptions:
            raise ExceptionGroup(
                f"{len(exceptions)} of {len(handlers)} notification handlers raised while "
                f"publishing {type(notification).__name__}",
                exceptions,
            )
