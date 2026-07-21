"""Synchronous notification handler for the mediator pattern."""

from abc import ABC, abstractmethod

from .._internal.notification import NotificationHandlerBaseMixin
from ..notification import Notification


class NotificationHandler[NotificationT: Notification](
    NotificationHandlerBaseMixin[NotificationT], ABC
):
    """Abstract base class for synchronous notification handlers.

    The sync mirror of `pymediate.NotificationHandler`: any number of sync notification
    handlers may subscribe to the same notification type, and the sync
    `Mediator.publish()` invokes every one of them sequentially, in
    registration order.

    The handler performs class-definition-time validation via __init_subclass__
    to ensure:
    - The __call__ method exists and is properly implemented
    - The __call__ method is synchronous (not async)
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
        Two handlers subscribed to one notification:
            ```python
            from dataclasses import dataclass

            from pymediate.sync import Notification, NotificationHandler, Mediator, Services

            @dataclass(frozen=True)
            class OrderPlaced(Notification):
                order_id: int
                item: str

            class SendConfirmation(NotificationHandler[OrderPlaced]):
                def __call__(self, notification: OrderPlaced) -> None:
                    print(f"confirming order {notification.order_id}")

            class UpdateAnalytics(NotificationHandler[OrderPlaced]):
                def __call__(self, notification: OrderPlaced) -> None:
                    print(f"recording order {notification.order_id}")

            services = Services()
            services.add(SendConfirmation()).add(UpdateAnalytics())
            mediator = Mediator(services.provider())

            mediator.publish(OrderPlaced(order_id=42, item="tea"))
            # confirming order 42
            # recording order 42
            ```

    Note:
        For asynchronous notification handlers, use ``pymediate.NotificationHandler`` instead.
        The two forms share one subscription registry, so every handler for an
        exact notification type must use the same form. If the ``__call__`` signature
        does not meet this contract, validation raises while Python defines the
        class, usually during import.

    Raises:
        InvalidHandlerSignatureError: If the __call__ signature is invalid,
            including a return annotation other than None.
        InvalidNotificationTypeError: If the notification type doesn't inherit from Notification.

    """

    _is_async = False  # Mark this as a synchronous notification handler

    @abstractmethod
    def __call__(self, notification: NotificationT) -> None:
        """Handle the published notification.

        This is an abstract method that must be implemented by all NotificationHandler
        subclasses, with the signature
        `def __call__(self, notification: NotificationType) -> None: ...`

        Args:
            notification: The notification to handle.

        Note:
            The annotation must be the exact notification class - a base class or
            union passes static checking (contravariance) but raises
            `InvalidHandlerSignatureError` at class definition. The return
            annotation must be `None`: publishing has no response, and any
            value a handler returns is discarded. This method must also be
            synchronous; for async notification handlers, use
            `pymediate.NotificationHandler`.
        """
        ...
