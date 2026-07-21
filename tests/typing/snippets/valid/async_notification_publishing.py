"""Async notification publishing through mediator.publish() - should pass mypy."""

import asyncio
from dataclasses import dataclass
from typing import override

from pymediate import Mediator, Notification, NotificationHandler, Services


@dataclass
class OrderPlaced(Notification):
    order_id: int


confirmed: list[int] = []
recorded: list[int] = []


class SendConfirmation(NotificationHandler[OrderPlaced]):
    @override
    async def __call__(self, notification: OrderPlaced) -> None:
        await asyncio.sleep(0.01)
        confirmed.append(notification.order_id)


class UpdateAnalytics(NotificationHandler[OrderPlaced]):
    @override
    async def __call__(self, notification: OrderPlaced) -> None:
        recorded.append(notification.order_id)


async def main() -> None:
    # Setup - N handlers may subscribe to one notification type
    provider = Services().add(SendConfirmation()).add(UpdateAnalytics()).provider()
    mediator = Mediator(provider)

    # publish accepts Notification instances, awaits all handlers concurrently
    await mediator.publish(OrderPlaced(order_id=42))

    assert confirmed == [42]
    assert recorded == [42]
