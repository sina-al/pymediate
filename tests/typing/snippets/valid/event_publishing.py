"""Typed event publishing through mediator.publish() - should pass mypy."""

from dataclasses import dataclass
from typing import override

from pymediate.sync import Event, EventHandler, Mediator, Services


@dataclass
class OrderPlaced(Event):
    order_id: int


confirmed: list[int] = []
recorded: list[int] = []


class SendConfirmation(EventHandler[OrderPlaced]):
    @override
    def __call__(self, event: OrderPlaced) -> None:
        confirmed.append(event.order_id)


class UpdateAnalytics(EventHandler[OrderPlaced]):
    @override
    def __call__(self, event: OrderPlaced) -> None:
        recorded.append(event.order_id)


# Setup - N handlers may subscribe to one event type
provider = Services().add(SendConfirmation()).add(UpdateAnalytics()).provider()
mediator = Mediator(provider)

# publish accepts Event instances and returns None
mediator.publish(OrderPlaced(order_id=42))

assert confirmed == [42]
assert recorded == [42]
