"""Synchronous event handler for the mediator pattern."""

from abc import ABC, abstractmethod

from .._internal.event import EventHandlerBaseMixin
from ..event import Event


class EventHandler[EventT: Event](EventHandlerBaseMixin[EventT], ABC):
    """Abstract base class for synchronous event handlers.

    The sync mirror of `pymediate.EventHandler`: any number of sync event
    handlers may subscribe to the same event type, and the sync
    `Mediator.publish()` invokes every one of them sequentially, in
    registration order.

    The handler performs class-definition-time validation via __init_subclass__
    to ensure:
    - The __call__ method exists and is properly implemented
    - The __call__ method is synchronous (not async)
    - The __call__ parameter annotates the exact declared event type
      (not a base class or union)
    - The __call__ return annotation is None - event handlers produce no response

    Validation runs when Python executes the handler's class body, usually
    during import and before the handler is instantiated.

    Type Parameters:
        EventT: The type of event this handler subscribes to. Must inherit
            from Event; static type checkers enforce the bound, and PyMediate
            validates it at class definition time.

    Examples:
        Two handlers subscribed to one event:
            ```python
            from dataclasses import dataclass

            from pymediate.sync import Event, EventHandler, Mediator, Services

            @dataclass(frozen=True)
            class OrderPlaced(Event):
                order_id: int
                item: str

            class SendConfirmation(EventHandler[OrderPlaced]):
                def __call__(self, event: OrderPlaced) -> None:
                    print(f"confirming order {event.order_id}")

            class UpdateAnalytics(EventHandler[OrderPlaced]):
                def __call__(self, event: OrderPlaced) -> None:
                    print(f"recording order {event.order_id}")

            services = Services()
            services.add(SendConfirmation()).add(UpdateAnalytics())
            mediator = Mediator(services.provider())

            mediator.publish(OrderPlaced(order_id=42, item="tea"))
            # confirming order 42
            # recording order 42
            ```

    Note:
        For asynchronous event handlers, use ``pymediate.EventHandler`` instead.
        The two forms share one subscription registry, so every handler for an
        exact event type must use the same form. If the ``__call__`` signature
        does not meet this contract, validation raises while Python defines the
        class, usually during import.

    Raises:
        InvalidHandlerSignatureError: If the __call__ signature is invalid,
            including a return annotation other than None.
        InvalidEventTypeError: If the event type doesn't inherit from Event.

    """

    _is_async = False  # Mark this as a synchronous event handler

    @abstractmethod
    def __call__(self, event: EventT) -> None:
        """Handle the published event.

        This is an abstract method that must be implemented by all EventHandler
        subclasses, with the signature
        `def __call__(self, event: EventType) -> None: ...`

        Args:
            event: The event to handle.

        Note:
            The annotation must be the exact event class - a base class or
            union passes static checking (contravariance) but raises
            `InvalidHandlerSignatureError` at class definition. The return
            annotation must be `None`: publishing has no response, and any
            value a handler returns is discarded. This method must also be
            synchronous; for async event handlers, use
            `pymediate.EventHandler`.
        """
        ...
