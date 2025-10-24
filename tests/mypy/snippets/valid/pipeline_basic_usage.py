"""Basic pipeline behavior type inference - should pass mypy."""

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
        print(f"Before: {request.username}")
        response = next()
        print(f"After: {response.user_id}")
        return response


# Pipeline type inference test
handler = CreateUserHandler()
logging = LoggingBehavior()
pipeline = Pipeline([logging], handler)

request = CreateUserRequest(username="alice")
response = pipeline(request)

# Mypy should infer response as UserResponse
user_id: int = response.user_id
username: str = response.username
