"""Parameterizing NotificationHandler with a non-Notification type - should fail mypy."""

from dataclasses import dataclass
from typing import override

from pymediate.sync import NotificationHandler


@dataclass
class NotAnEvent:
    order_id: int


# ERROR: NotificationHandler's type parameter is bound to Notification
class SendConfirmation(NotificationHandler[NotAnEvent]):
    @override
    def __call__(self, notification: NotAnEvent) -> None:
        pass
