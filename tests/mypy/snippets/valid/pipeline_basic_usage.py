"""Behavior authoring and typed dispatch through the mediator - should pass mypy."""

from collections.abc import Callable
from dataclasses import dataclass

from pymediate import Handler, Mediator, PipelineBehavior, Request, Services


@dataclass
class UserResponse:
    user_id: int
    username: str


@dataclass
class CreateUserRequest(Request[UserResponse]):
    username: str


class CreateUserHandler(Handler[CreateUserRequest]):
    def __call__(self, request: CreateUserRequest) -> UserResponse:
        return UserResponse(user_id=1, username=request.username)


class LoggingBehavior(PipelineBehavior[CreateUserRequest]):
    def __call__(
        self, request: CreateUserRequest, next: Callable[[], UserResponse]
    ) -> UserResponse:
        print(f"Before: {request.username}")
        response = next()
        print(f"After: {response.user_id}")
        return response


services = Services()
services.add(LoggingBehavior())
services.add(CreateUserHandler())
mediator = Mediator(services.provider())

request = CreateUserRequest(username="alice")
response = mediator.send(request)

# Mypy should infer response as UserResponse, behaviors notwithstanding
user_id: int = response.user_id
username: str = response.username
