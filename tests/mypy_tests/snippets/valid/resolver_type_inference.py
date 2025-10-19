"""Resolver.resolve() returns correctly typed handler - should pass mypy."""

from dataclasses import dataclass

from pymediate import Handler, Request, SimpleResolver


@dataclass
class UserResponse:
    user_id: int


@dataclass
class GetUserRequest(Request[UserResponse]):
    user_id: int


class GetUserHandler(Handler[GetUserRequest]):
    def __call__(self, request: GetUserRequest) -> UserResponse:
        return UserResponse(user_id=1)


# Setup
resolver = SimpleResolver()
resolver.register(GetUserRequest, GetUserHandler())

# Resolver should return correctly typed handler
handler = resolver.resolve(GetUserRequest)

# Mypy should know handler accepts GetUserRequest and returns UserResponse
request = GetUserRequest(user_id=1)
response = handler(request)

# Response should be typed as UserResponse
user_id: int = response.user_id
