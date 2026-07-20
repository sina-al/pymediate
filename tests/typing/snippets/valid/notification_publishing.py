"""Typed notification publishing through mediator.publish() - should pass mypy."""

from dataclasses import dataclass
from typing import override

from pymediate.sync import Mediator, Notification, NotificationHandler, Services


@dataclass
class OrderPlaced(Notification):
    order_id: int


confirmed: list[int] = []
recorded: list[int] = []


class SendConfirmation(NotificationHandler[OrderPlaced]):
    @override
    def __call__(self, notification: OrderPlaced) -> None:
        confirmed.append(notification.order_id)


class UpdateAnalytics(NotificationHandler[OrderPlaced]):
    @override
    def __call__(self, notification: OrderPlaced) -> None:
        recorded.append(notification.order_id)


# Setup - N handlers may subscribe to one notification type
provider = Services().add(SendConfirmation()).add(UpdateAnalytics()).provider()
mediator = Mediator(provider)

# publish accepts Notification instances and returns None
mediator.publish(OrderPlaced(order_id=42))

assert confirmed == [42]
assert recorded == [42]
