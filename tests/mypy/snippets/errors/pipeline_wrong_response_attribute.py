"""Accessing non-existent attribute on pipeline response - should fail mypy."""

from dataclasses import dataclass

from pymediate import Handler, Request
from pymediate.pipeline import Pipeline


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


class LoggingBehavior:
    def __call__(self, request: CreateUserRequest, next):  # type: ignore[no-untyped-def]
        return next()


handler = CreateUserHandler()
pipeline = Pipeline([LoggingBehavior()], handler)

request = CreateUserRequest(username="alice")
response = pipeline(request)

# This should fail - UserResponse doesn't have an 'email' attribute
email: str = response.email  # type: ignore[attr-defined]
