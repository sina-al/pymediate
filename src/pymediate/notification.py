"""Notification base class and asynchronous notification handler for the mediator pattern."""

from abc import ABC, abstractmethod

from ._internal.notification import NotificationHandlerBaseMixin


class Notification:
    """Base class for notifications published to zero or more handlers.

    Where a `Request[ResponseT]` is sent to exactly one handler and returns its
    typed response, an `Notification` is published to every handler subscribed to its
    exact type - zero, one, or many - and returns nothing. Inherit from `Notification`
    to make a class publishable via `Mediator.publish()`.

    Notifications carry no response type parameter, and handlers must be annotated to
    return ``None``. ``publish()`` completes after the subscribed handlers finish.

    Notification subclasses can be dataclasses or regular classes.

    Examples:
        Defining and publishing a notification:
            ```python
            import asyncio
            from dataclasses import dataclass

            from pymediate import Notification, NotificationHandler, Mediator, Services

            @dataclass(frozen=True)
            class OrderPlaced(Notification):
                order_id: int
                item: str

            class SendConfirmation(NotificationHandler[OrderPlaced]):
                async def __call__(self, notification: OrderPlaced) -> None:
                    print(f"confirming order {notification.order_id}")

            async def main():
                services = Services()
                services.add(SendConfirmation())
                mediator = Mediator(services.provider())

                await mediator.publish(OrderPlaced(order_id=42, item="tea"))

            asyncio.run(main())
            ```

    Note:
        Publishing dispatches on the exact class of the notification instance - a
        handler subscribed to a base notification class does not receive derived
        notifications. This mirrors how requests dispatch to handlers. The same
        ``Notification`` base and process-wide subscription registry are shared by the
        asynchronous and synchronous APIs. For one exact notification type, define all
        handlers with ``pymediate.NotificationHandler`` or all with
        ``pymediate.sync.NotificationHandler``; do not mix the forms.

    """


class NotificationHandler[NotificationT: Notification](
    NotificationHandlerBaseMixin[NotificationT], ABC
):
    """Abstract base class for asynchronous notification handlers.

    Notification handlers contain the logic that reacts to a published notification. Unlike
    request handlers, any number of notification handlers may subscribe to the same
    notification type. ``Mediator.publish()`` runs them concurrently.

    The handler performs class-definition-time validation via __init_subclass__
    to ensure:
    - The __call__ method exists and is properly implemented
    - The __call__ method is asynchronous (async def)
    - The __call__ parameter annotates the exact declared notification type
      (not a base class or union)
    - The __call__ return annotation is None - notification handlers produce no response

    Validation runs when Python executes the handler's class body, usually
    during import and before the handler is instantiated.

    Type Parameters:
        NotificationT: The type of notification this handler subscribes to. Must inherit
            from Notification; static type checkers enforce the bound, and PyMediate
            validates it at class definition time.

    Examples:
        Two async handlers subscribed to one notification:
            ```python
            import asyncio
            from dataclasses import dataclass

            from pymediate import Notification, NotificationHandler, Mediator, Services

            @dataclass(frozen=True)
            class OrderPlaced(Notification):
                order_id: int
                item: str

            class SendConfirmation(NotificationHandler[OrderPlaced]):
                async def __call__(self, notification: OrderPlaced) -> None:
                    print(f"confirming order {notification.order_id}")

            class UpdateAnalytics(NotificationHandler[OrderPlaced]):
                async def __call__(self, notification: OrderPlaced) -> None:
                    print(f"recording order {notification.order_id}")

            async def main():
                services = Services()
                services.add(SendConfirmation()).add(UpdateAnalytics())
                mediator = Mediator(services.provider())

                await mediator.publish(OrderPlaced(order_id=42, item="tea"))

            asyncio.run(main())
            ```

    Note:
        Handlers for the same notification run concurrently, so they must not rely on
        each other's effects or mutate shared state without synchronization.
        For synchronous notification handlers, use ``pymediate.sync.NotificationHandler``
        instead. The two forms share one subscription registry, so every handler
        for an exact notification type must use the same form. If the ``__call__``
        signature does not meet this contract, validation raises while Python
        defines the class, usually during import.

    Raises:
        InvalidHandlerSignatureError: If the __call__ signature is invalid or
            not async, including a return annotation other than None.
        InvalidNotificationTypeError: If the notification type doesn't inherit from Notification.

    """

    _is_async = True  # Mark this as an asynchronous notification handler

    @abstractmethod
    async def __call__(self, notification: NotificationT) -> None:
        """Handle the published notification asynchronously.

        This is an abstract method that must be implemented by all async
        NotificationHandler subclasses, with the signature
        `async def __call__(self, notification: NotificationType) -> None: ...`

        Args:
            notification: The notification to handle.

        Note:
            The annotation must be the exact notification class - a base class or
            union passes static checking (contravariance) but raises
            `InvalidHandlerSignatureError` at class definition. The return
            annotation must be `None`: publishing has no response, and any
            value a handler returns is discarded. This method must also be
            asynchronous (`async def`); for sync notification handlers, use
            `pymediate.sync.NotificationHandler`.
        """
        ...
