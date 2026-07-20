"""Parameterizing NotificationHandler with a non-Notification type - should fail mypy."""

from dataclasses import dataclass
from typing import override

from pymediate.sync import NotificationHandler


@dataclass
class NotANotification:
    order_id: int


# ERROR: NotificationHandler's type parameter is bound to Notification
class SendConfirmation(NotificationHandler[NotANotification]):
    @override
    def __call__(self, notification: NotANotification) -> None:
        pass
