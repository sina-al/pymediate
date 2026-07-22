"""ServiceProvider.__getitem__ returns correctly typed handler - should pass mypy."""

from dataclasses import dataclass
from typing import override

from pymediate.sync import Request, RequestHandler, Services


@dataclass
class UserResponse:
    user_id: int


@dataclass
class GetUserRequest(Request[UserResponse]):
    user_id: int


class GetUserHandler(RequestHandler[GetUserRequest]):
    @override
    def __call__(self, request: GetUserRequest) -> UserResponse:
        return UserResponse(user_id=1)


# Setup
provider = Services().add(GetUserHandler()).provider()

# ServiceProvider should return correctly typed handler
handler = provider[GetUserHandler]

# Mypy should know handler accepts GetUserRequest and returns UserResponse
request = GetUserRequest(user_id=1)
response = handler(request)

# Response should be typed as UserResponse
user_id: int = response.user_id
