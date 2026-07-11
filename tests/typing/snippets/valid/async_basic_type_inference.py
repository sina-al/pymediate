"""Basic async type inference through mediator.send() - should pass mypy."""

import asyncio
from dataclasses import dataclass
from typing import override

from pymediate import Request, Services
from pymediate.aio import Mediator, RequestHandler


@dataclass
class UserResponse:
    user_id: int
    username: str


@dataclass
class GetUserRequest(Request[UserResponse]):
    user_id: int


class GetUserHandler(RequestHandler[GetUserRequest]):
    @override
    async def __call__(self, request: GetUserRequest) -> UserResponse:
        await asyncio.sleep(0.01)
        return UserResponse(user_id=request.user_id, username="alice")


async def main() -> None:
    # Setup
    provider = Services().add(GetUserHandler()).provider()
    mediator = Mediator(provider)

    # Type inference test: the checker should know response is UserResponse
    request = GetUserRequest(user_id=1)
    response = await mediator.send(request)
    assert response.username == "alice"
