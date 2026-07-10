"""Expecting the wrong response type with a behavior registered - should fail mypy."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from pymediate import Handler, Mediator, PipelineBehavior, Request, Services


@dataclass
class UserResponse:
    user_id: int
    username: str


@dataclass
class OrderResponse:
    order_id: int


@dataclass
class CreateUserRequest(Request[UserResponse]):
    username: str


class CreateUserHandler(Handler[CreateUserRequest]):
    @override
    def __call__(self, request: CreateUserRequest) -> UserResponse:
        return UserResponse(user_id=1, username=request.username)


class LoggingBehavior(PipelineBehavior[CreateUserRequest]):
    @override
    def __call__(
        self, request: CreateUserRequest, next: Callable[[], UserResponse]
    ) -> UserResponse:
        return next()


provider = Services().add(LoggingBehavior()).add(CreateUserHandler()).provider()
mediator = Mediator(provider)

request = CreateUserRequest(username="alice")
response = mediator.send(request)

# This should fail - behaviors don't change the response type: it's UserResponse,
# not OrderResponse
order_response: OrderResponse = response
