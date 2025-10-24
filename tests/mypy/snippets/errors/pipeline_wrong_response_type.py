"""Expecting wrong response type from pipeline - should fail mypy."""

from dataclasses import dataclass

from pymediate import Handler, Request
from pymediate.pipeline import Pipeline


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
    def __call__(self, request: CreateUserRequest) -> UserResponse:
        return UserResponse(user_id=1, username=request.username)


class LoggingBehavior:
    def __call__(self, request: CreateUserRequest, next):  # type: ignore[no-untyped-def]
        return next()


handler = CreateUserHandler()
pipeline = Pipeline([LoggingBehavior()], handler)

request = CreateUserRequest(username="alice")
response = pipeline(request)

# This should fail - response is UserResponse, not OrderResponse
order_response: OrderResponse = response  # type: ignore[assignment]
