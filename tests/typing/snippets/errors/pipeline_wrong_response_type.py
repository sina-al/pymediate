"""Expecting the wrong response type with a behavior registered - should fail mypy."""

from dataclasses import dataclass
from typing import override

from pymediate.sync import Mediator, Next, PipelineBehavior, Request, RequestHandler, Services


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


class CreateUserHandler(RequestHandler[CreateUserRequest]):
    @override
    def __call__(self, request: CreateUserRequest) -> UserResponse:
        return UserResponse(user_id=1, username=request.username)


class LoggingBehavior(PipelineBehavior[CreateUserRequest]):
    @override
    def __call__(self, request: CreateUserRequest, next: Next[UserResponse]) -> UserResponse:
        return next()


provider = Services().add(LoggingBehavior()).add(CreateUserHandler()).provider()
mediator = Mediator(provider, behaviors=[LoggingBehavior])

request = CreateUserRequest(username="alice")
response = mediator.send(request)

# This should fail - behaviors don't change the response type: it's UserResponse,
# not OrderResponse
order_response: OrderResponse = response
