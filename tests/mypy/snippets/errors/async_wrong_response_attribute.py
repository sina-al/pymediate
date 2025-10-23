"""Accessing non-existent attribute on async response - should fail mypy."""

import asyncio
from dataclasses import dataclass

from pymediate import Request, Services
from pymediate.aio import Handler, Mediator


@dataclass
class UserResponse:
    user_id: int
    username: str


@dataclass
class GetUserRequest(Request[UserResponse]):
    user_id: int


class GetUserHandler(Handler[GetUserRequest]):
    async def __call__(self, request: GetUserRequest) -> UserResponse:
        await asyncio.sleep(0.01)
        return UserResponse(user_id=request.user_id, username="alice")


async def main() -> None:
    services = Services()
    services.add(GetUserRequest, GetUserHandler())
    provider = services.provider()
    mediator = Mediator(provider)

    response = await mediator.send(GetUserRequest(user_id=1))

    # ERROR: UserResponse has no attribute 'email'
    email = response.email  # noqa: F841
