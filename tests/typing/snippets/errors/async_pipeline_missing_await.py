"""Missing await on async mediator dispatch with a behavior - should fail mypy."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import override

from pymediate import Mediator, PipelineBehavior, Request, RequestHandler, Services


@dataclass
class UserResponse:
    user_id: int


@dataclass
class CreateUserRequest(Request[UserResponse]):
    username: str


class CreateUserHandler(RequestHandler[CreateUserRequest]):
    @override
    async def __call__(self, request: CreateUserRequest) -> UserResponse:
        return UserResponse(user_id=1)


class AsyncLoggingBehavior(PipelineBehavior[CreateUserRequest]):
    @override
    async def __call__(
        self,
        request: CreateUserRequest,
        next: Callable[[], Awaitable[UserResponse]],
    ) -> UserResponse:
        return await next()


async def main() -> None:
    provider = Services().add(AsyncLoggingBehavior()).add(CreateUserHandler()).provider()
    mediator = Mediator(provider)

    request = CreateUserRequest(username="alice")

    # This should fail - missing await, so response is a coroutine, not UserResponse
    response = mediator.send(request)
    user_id: int = response.user_id
    _ = user_id  # Use the variable to satisfy ruff


asyncio.run(main())
