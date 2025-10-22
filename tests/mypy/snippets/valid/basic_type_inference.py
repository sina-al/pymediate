"""Basic type inference through mediator.send() - should pass mypy."""

from dataclasses import dataclass

from pymediate import Handler, Mediator, Request, SimpleResolver


@dataclass
class UserResponse:
    user_id: int
    username: str


@dataclass
class GetUserRequest(Request[UserResponse]):
    user_id: int


class GetUserHandler(Handler[GetUserRequest]):
    def __call__(self, request: GetUserRequest) -> UserResponse:
        return UserResponse(user_id=request.user_id, username="alice")


# Setup
resolver = SimpleResolver()
resolver.register(GetUserRequest, GetUserHandler())
mediator = Mediator(resolver)

# Type inference test
request = GetUserRequest(user_id=1)
response = mediator.send(request)

# Mypy should know response is UserResponse
user_id: int = response.user_id
username: str = response.username
