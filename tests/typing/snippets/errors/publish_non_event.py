"""Publishing something that isn't an Event - should fail mypy."""

from dataclasses import dataclass
from typing import override

from pymediate.sync import Event, EventHandler, Mediator, Request, Services


@dataclass
class UserResponse:
    user_id: int


@dataclass
class GetUserRequest(Request[UserResponse]):
    user_id: int


@dataclass
class OrderPlaced(Event):
    order_id: int


class SendConfirmation(EventHandler[OrderPlaced]):
    @override
    def __call__(self, event: OrderPlaced) -> None:
        pass


provider = Services().add(SendConfirmation()).provider()
mediator = Mediator(provider)

# ERROR: publish takes an Event; a Request is not publishable
mediator.publish(GetUserRequest(user_id=1))
