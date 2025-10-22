"""Basic async type inference through mediator.send() - should pass mypy."""

import asyncio
from dataclasses import dataclass

from pymediate import Request, SimpleResolver
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
    # Setup
    resolver = SimpleResolver()
    resolver.register(GetUserRequest, GetUserHandler())
    mediator = Mediator(resolver)

    # Type inference test
    request = GetUserRequest(user_id=1)
    response = await mediator.send(request)

    # Mypy should know response is UserResponse
    user_id: int = response.user_id
    username: str = response.username
