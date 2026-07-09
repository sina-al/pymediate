"""Async behavior authoring and typed dispatch through the mediator - should pass mypy."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from pymediate import Request, Services
from pymediate.aio import Handler, Mediator, PipelineBehavior


@dataclass
class UserResponse:
    user_id: int
    username: str


@dataclass
class CreateUserRequest(Request[UserResponse]):
    username: str


class CreateUserHandler(Handler[CreateUserRequest]):
    async def __call__(self, request: CreateUserRequest) -> UserResponse:
        await asyncio.sleep(0.01)
        return UserResponse(user_id=1, username=request.username)


class AsyncLoggingBehavior(PipelineBehavior[CreateUserRequest]):
    async def __call__(
        self,
        request: CreateUserRequest,
        next: Callable[[], Awaitable[UserResponse]],
    ) -> UserResponse:
        print(f"Before: {request.username}")
        response = await next()
        print(f"After: {response.user_id}")
        return response


async def main() -> None:
    services = Services()
    services.add(AsyncLoggingBehavior())
    services.add(CreateUserHandler())
    mediator = Mediator(services.provider())

    request = CreateUserRequest(username="alice")
    response = await mediator.send(request)

    # Mypy should infer response as UserResponse
    user_id: int = response.user_id
    username: str = response.username
    assert user_id == 1
    assert username == "alice"


# Run the async code
asyncio.run(main())
