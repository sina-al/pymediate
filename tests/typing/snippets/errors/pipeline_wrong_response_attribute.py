"""Accessing a non-existent attribute with a behavior registered - should fail mypy."""

from dataclasses import dataclass
from typing import override

from pymediate.sync import Mediator, Next, PipelineBehavior, Request, RequestHandler, Services


@dataclass
class UserResponse:
    user_id: int
    username: str


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
mediator = Mediator(provider)

request = CreateUserRequest(username="alice")
response = mediator.send(request)

# This should fail - UserResponse doesn't have an 'email' attribute
email: str = response.email
