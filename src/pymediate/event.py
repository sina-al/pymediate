"""Event base class and asynchronous event handler for the mediator pattern."""

from abc import ABC, abstractmethod

from ._internal.event import EventHandlerBaseMixin


class Event:
    """Base class for events published to zero or more handlers.

    Where a `Request[ResponseT]` is sent to exactly one handler and returns its
    typed response, an `Event` is published to every handler subscribed to its
    exact type - zero, one, or many - and returns nothing. Inherit from `Event`
    to make a class publishable via `Mediator.publish()`.

    Events carry no response type parameter: publishing is fire-and-notify, so
    there is nothing to infer and handlers must be annotated to return `None`.

    This class works seamlessly with dataclasses, regular classes, and any
    Python class structure.

    Examples:
        Defining and publishing an event:
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

            async def main():
                services = Services()
                services.add(SendConfirmation())
                mediator = Mediator(services.provider())

                await mediator.publish(OrderPlaced(order_id=42))

            asyncio.run(main())
            ```

    Note:
        Publishing dispatches on the exact class of the event instance - a
        handler subscribed to a base event class does not receive derived
        events. This mirrors how requests dispatch to handlers. The same
        `Event` base works on both sides of the library: subscribe async
        handlers (`pymediate.EventHandler`) or sync ones
        (`pymediate.sync.EventHandler`) to it.

    See Also:
        - EventHandler: Base class for async handlers that subscribe to an event.
        - Mediator.publish: Publishes an event to all its handlers.
        - Request: The one-handler, typed-response counterpart.
        - pymediate.sync.EventHandler: Sync event handler variant.
    """


class EventHandler[EventT: Event](EventHandlerBaseMixin[EventT], ABC):
    """Abstract base class for asynchronous event handlers.

    Event handlers contain the logic that reacts to a published event. Unlike
    request handlers, any number of event handlers may subscribe to the same
    event type - `Mediator.publish()` runs all of them concurrently via
    `asyncio.gather` (tasks are created in registration order).

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
        Handlers for the same event run concurrently, so they must not rely on
        each other's effects or mutate shared state without synchronization.
        For synchronous event handlers, use `pymediate.sync.EventHandler`
        instead. Validation occurs at class definition time: if your __call__
        signature doesn't match expectations, you'll get a clear error message
        when the module is imported, not when the event is published.

    Raises:
        InvalidHandlerSignatureError: If the __call__ signature is invalid or
            not async, including a return annotation other than None.
        InvalidEventTypeError: If the event type doesn't inherit from Event.

    See Also:
        - Event: Base event class.
        - Mediator.publish: Publishes an event to all its handlers.
        - pymediate.sync.EventHandler: Sync event handler variant.
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
            `pymediate.sync.EventHandler`.
        """
        ...
