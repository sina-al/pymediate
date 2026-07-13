"""Behavior authoring and typed dispatch through the mediator - should pass mypy."""

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
        print(f"Before: {request.username}")
        response = next()
        print(f"After: {response.user_id}")
        return response


provider = Services().add(LoggingBehavior()).add(CreateUserHandler()).provider()
mediator = Mediator(provider)

request = CreateUserRequest(username="alice")
response = mediator.send(request)

# Mypy should infer response as UserResponse, behaviors notwithstanding
user_id: int = response.user_id
username: str = response.username
