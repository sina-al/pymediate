"""Streaming a normal Request through stream() instead of send() - should fail mypy."""

from dataclasses import dataclass
from typing import override

from pymediate.sync import Mediator, Request, RequestHandler, Services


@dataclass
class UserResponse:
    user_id: int


@dataclass
class GetUserRequest(Request[UserResponse]):
    user_id: int


class GetUserHandler(RequestHandler[GetUserRequest]):
    @override
    def __call__(self, request: GetUserRequest) -> UserResponse:
        return UserResponse(user_id=request.user_id)


provider = Services().add(GetUserHandler()).provider()
mediator = Mediator(provider)

# ERROR: stream takes a StreamRequest; a Request is dispatched with send()
mediator.stream(GetUserRequest(user_id=1))
