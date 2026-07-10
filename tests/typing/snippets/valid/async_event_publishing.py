"""Async event publishing through mediator.publish() - should pass mypy."""

import asyncio
from dataclasses import dataclass
from typing import override

from pymediate import Event, Services
from pymediate.aio import EventHandler, Mediator


@dataclass
class OrderPlaced(Event):
    order_id: int


confirmed: list[int] = []
recorded: list[int] = []


class SendConfirmation(EventHandler[OrderPlaced]):
    @override
    async def __call__(self, event: OrderPlaced) -> None:
        await asyncio.sleep(0.01)
        confirmed.append(event.order_id)


class UpdateAnalytics(EventHandler[OrderPlaced]):
    @override
    async def __call__(self, event: OrderPlaced) -> None:
        recorded.append(event.order_id)


async def main() -> None:
    # Setup - N handlers may subscribe to one event type
    provider = Services().add(SendConfirmation()).add(UpdateAnalytics()).provider()
    mediator = Mediator(provider)

    # publish accepts Event instances, awaits all handlers concurrently
    await mediator.publish(OrderPlaced(order_id=42))

    assert confirmed == [42]
    assert recorded == [42]
