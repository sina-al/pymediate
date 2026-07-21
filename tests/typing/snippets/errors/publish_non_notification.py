"""Publishing something that isn't a Notification - should fail mypy."""

from dataclasses import dataclass
from typing import override

from pymediate.sync import Mediator, Notification, NotificationHandler, Request, Services


@dataclass
class UserResponse:
    user_id: int


@dataclass
class GetUserRequest(Request[UserResponse]):
    user_id: int


@dataclass
class OrderPlaced(Notification):
    order_id: int


class SendConfirmation(NotificationHandler[OrderPlaced]):
    @override
    def __call__(self, notification: OrderPlaced) -> None:
        pass


provider = Services().add(SendConfirmation()).provider()
mediator = Mediator(provider)

# ERROR: publish takes a Notification; a Request is not publishable
mediator.publish(GetUserRequest(user_id=1))
