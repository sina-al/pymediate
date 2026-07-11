"""Accessing non-existent response attribute - should fail mypy."""

from dataclasses import dataclass
from typing import override

from pymediate import Mediator, Request, RequestHandler, Services


@dataclass
class UserResponse:
    user_id: int
    username: str


@dataclass
class GetUserRequest(Request[UserResponse]):
    user_id: int


class GetUserHandler(RequestHandler[GetUserRequest]):
    @override
    def __call__(self, request: GetUserRequest) -> UserResponse:
        return UserResponse(user_id=request.user_id, username="alice")


provider = Services().add(GetUserHandler()).provider()
mediator = Mediator(provider)

request = GetUserRequest(user_id=1)
response = mediator.send(request)

# ERROR: UserResponse has no attribute 'email'
email = response.email
