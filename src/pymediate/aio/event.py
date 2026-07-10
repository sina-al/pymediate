"""Asynchronous event handler for the mediator pattern."""

from abc import ABC, abstractmethod

from .._internal.event import EventHandlerBaseMixin
from ..event import Event


class EventHandler[EventT: Event](EventHandlerBaseMixin[EventT], ABC):
    """Abstract base class for asynchronous event handlers.

    The async mirror of `pymediate.EventHandler`: any number of async event
    handlers may subscribe to the same event type, and the async
    `Mediator.publish()` runs all of them concurrently via `asyncio.gather`
    (tasks are created in registration order).

    The handler performs class-definition-time validation via __init_subclass__
    to ensure:
    - The __call__ method exists and is properly implemented
    - The __call__ method is asynchronous (async def)
    - The __call__ parameter annotates the exact declared event type
      (not a base class or union)
    - The __call__ return annotation is None - event handlers produce no response

    This validation happens at class definition time (import time), catching
    errors early in the development cycle rather than at runtime.

    Type Parameters:
        EventT: The type of event this handler subscribes to. Must inherit
            from Event; static type checkers enforce the bound, and PyMediate
            validates it at class definition time.

    Examples:
        Two async handlers subscribed to one event:
            ```python
            import asyncio
            from dataclasses import dataclass
            from pymediate import Event, Services
            from pymediate.aio import EventHandler, Mediator

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
        Handlers for the same event run concurrently, so they must not rely on
        each other's effects or mutate shared state without synchronization.
        For synchronous event handlers, use `pymediate.EventHandler` instead.

    Raises:
        InvalidHandlerSignatureError: If the __call__ signature is invalid or
            not async, including a return annotation other than None.
        InvalidEventTypeError: If the event type doesn't inherit from Event.

    See Also:
        - Event: Base event class.
        - pymediate.aio.Mediator.publish: Publishes an event to all its handlers.
        - pymediate.EventHandler: Sync event handler variant.
    """

    _is_async = True  # Mark this as an asynchronous event handler

    @abstractmethod
    async def __call__(self, event: EventT) -> None:
        """Handle the published event asynchronously.

        This is an abstract method that must be implemented by all async
        EventHandler subclasses, with the signature
        `async def __call__(self, event: EventType) -> None: ...`

        Args:
            event: The event to handle.

        Note:
            The annotation must be the exact event class - a base class or
            union passes static checking (contravariance) but raises
            `InvalidHandlerSignatureError` at class definition. The return
            annotation must be `None`: publishing has no response, and any
            value a handler returns is discarded. This method must also be
            asynchronous (`async def`); for sync event handlers, use
            `pymediate.EventHandler`.
        """
        ...
