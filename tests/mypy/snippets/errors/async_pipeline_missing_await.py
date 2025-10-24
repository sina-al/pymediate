"""Missing await on async pipeline - should fail mypy."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from pymediate import Request
from pymediate.aio import Handler
from pymediate.aio.pipeline import Pipeline


@dataclass
class UserResponse:
    user_id: int


@dataclass
class CreateUserRequest(Request[UserResponse]):
    username: str


class CreateUserHandler(Handler[CreateUserRequest]):
    async def __call__(self, request: CreateUserRequest) -> UserResponse:
        return UserResponse(user_id=1)


class AsyncLoggingBehavior:
    async def __call__(
        self,
        request: CreateUserRequest,
        next: Callable[[], Awaitable[UserResponse]],
    ) -> UserResponse:
        return await next()


async def main() -> None:
    handler = CreateUserHandler()
    pipeline = Pipeline([AsyncLoggingBehavior()], handler)

    request = CreateUserRequest(username="alice")

    # This should fail - missing await on async pipeline call
    response = pipeline(request)  # type: ignore[misc]

    # This would fail at runtime too, but mypy should catch it
    user_id: int = response.user_id  # type: ignore[union-attr]
    _ = user_id  # Use the variable to satisfy ruff


asyncio.run(main())
