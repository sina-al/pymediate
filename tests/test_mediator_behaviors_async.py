"""Tests for async mediator integration with pipeline behaviors."""

import asyncio
from dataclasses import dataclass

import pytest

from pymediate import Mediator, PipelineBehavior, Request, RequestHandler, Services


@pytest.mark.asyncio
async def test_async_mediator_without_behaviors() -> None:
    """Test async mediator without behaviors calls handler directly."""

    @dataclass
    class UserResponse:
        user_id: int
        username: str

    @dataclass
    class CreateUserRequest(Request[UserResponse]):
        username: str

    class AsyncCreateUserHandler(RequestHandler[CreateUserRequest]):
        async def __call__(self, request: CreateUserRequest) -> UserResponse:
            await asyncio.sleep(0.001)
            return UserResponse(user_id=1, username=request.username)

    services = Services()
    services.add(AsyncCreateUserHandler())
    provider = services.provider()

    mediator = Mediator(provider)
    response = await mediator.send(CreateUserRequest(username="alice"))

    assert response.user_id == 1
    assert response.username == "alice"


@pytest.mark.asyncio
async def test_async_mediator_with_single_behavior() -> None:
    """Test async mediator with a single pipeline behavior."""

    @dataclass
    class UserResponse:
        user_id: int
        username: str

    @dataclass
    class CreateUserRequest(Request[UserResponse]):
        username: str

    class AsyncCreateUserHandler(RequestHandler[CreateUserRequest]):
        async def __call__(self, request: CreateUserRequest) -> UserResponse:
            await asyncio.sleep(0.001)
            return UserResponse(user_id=1, username=request.username)

    log: list[str] = []

    class AsyncLoggingBehavior(PipelineBehavior[CreateUserRequest]):
        async def __call__(self, request, next):  # type: ignore[no-untyped-def]
            log.append("logging:before")
            response = await next()
            log.append("logging:after")
            return response

    services = Services()
    services.add(AsyncLoggingBehavior())
    services.add(AsyncCreateUserHandler())
    provider = services.provider()

    mediator = Mediator(provider)
    response = await mediator.send(CreateUserRequest(username="alice"))

    assert response.user_id == 1
    assert response.username == "alice"
    assert log == ["logging:before", "logging:after"]


@pytest.mark.asyncio
async def test_async_mediator_with_multiple_behaviors() -> None:
    """Test multiple async behaviors execute in registration order."""

    @dataclass
    class UserResponse:
        user_id: int
        username: str

    @dataclass
    class CreateUserRequest(Request[UserResponse]):
        username: str

    class AsyncCreateUserHandler(RequestHandler[CreateUserRequest]):
        async def __call__(self, request: CreateUserRequest) -> UserResponse:
            await asyncio.sleep(0.001)
            return UserResponse(user_id=1, username=request.username)

    log: list[str] = []

    class AsyncLoggingBehavior(PipelineBehavior[CreateUserRequest]):
        async def __call__(self, request, next):  # type: ignore[no-untyped-def]
            log.append("logging:before")
            response = await next()
            log.append("logging:after")
            return response

    class AsyncTimingBehavior(PipelineBehavior[CreateUserRequest]):
        async def __call__(self, request, next):  # type: ignore[no-untyped-def]
            log.append("timing:before")
            response = await next()
            log.append("timing:after")
            return response

    services = Services()
    services.add(AsyncLoggingBehavior())  # Outermost
    services.add(AsyncTimingBehavior())  # Inner
    services.add(AsyncCreateUserHandler())
    provider = services.provider()

    mediator = Mediator(provider)
    response = await mediator.send(CreateUserRequest(username="alice"))

    assert response.user_id == 1
    assert log == [
        "logging:before",
        "timing:before",
        "timing:after",
        "logging:after",
    ]


@pytest.mark.asyncio
async def test_async_mediator_behaviors_can_modify_response() -> None:
    """Test async behaviors can modify the response."""

    @dataclass
    class UserResponse:
        user_id: int
        username: str

    @dataclass
    class CreateUserRequest(Request[UserResponse]):
        username: str

    class AsyncCreateUserHandler(RequestHandler[CreateUserRequest]):
        async def __call__(self, request: CreateUserRequest) -> UserResponse:
            await asyncio.sleep(0.001)
            return UserResponse(user_id=1, username=request.username)

    class AsyncResponseModifyingBehavior(PipelineBehavior[CreateUserRequest]):
        async def __call__(self, request, next):  # type: ignore[no-untyped-def]
            response = await next()
            await asyncio.sleep(0.001)
            response.username = response.username + "_modified"
            return response

    services = Services()
    services.add(AsyncResponseModifyingBehavior())
    services.add(AsyncCreateUserHandler())
    provider = services.provider()

    mediator = Mediator(provider)
    response = await mediator.send(CreateUserRequest(username="alice"))

    assert response.user_id == 1
    assert response.username == "alice_modified"


@pytest.mark.asyncio
async def test_async_mediator_behavior_can_short_circuit() -> None:
    """Test async behavior can short-circuit by not calling next."""

    @dataclass
    class UserResponse:
        user_id: int
        username: str

    @dataclass
    class CreateUserRequest(Request[UserResponse]):
        username: str

    class AsyncCreateUserHandler(RequestHandler[CreateUserRequest]):
        async def __call__(self, request: CreateUserRequest) -> UserResponse:
            await asyncio.sleep(0.001)
            return UserResponse(user_id=1, username=request.username)

    class AsyncShortCircuitBehavior(PipelineBehavior[CreateUserRequest]):
        async def __call__(self, request, next):  # type: ignore[no-untyped-def]
            await asyncio.sleep(0.001)
            # Don't call next - return early
            return UserResponse(user_id=-1, username="short-circuited")

    services = Services()
    services.add(AsyncShortCircuitBehavior())
    services.add(AsyncCreateUserHandler())
    provider = services.provider()

    mediator = Mediator(provider)
    response = await mediator.send(CreateUserRequest(username="alice"))

    # RequestHandler should not be called
    assert response.user_id == -1
    assert response.username == "short-circuited"


@pytest.mark.asyncio
async def test_async_mediator_validation_behavior() -> None:
    """Test async validation behavior that can reject invalid requests."""

    @dataclass
    class UserResponse:
        user_id: int
        username: str

    @dataclass
    class CreateUserRequest(Request[UserResponse]):
        username: str

    class AsyncCreateUserHandler(RequestHandler[CreateUserRequest]):
        async def __call__(self, request: CreateUserRequest) -> UserResponse:
            await asyncio.sleep(0.001)
            return UserResponse(user_id=1, username=request.username)

    class AsyncValidationBehavior(PipelineBehavior[CreateUserRequest]):
        async def __call__(self, request, next):  # type: ignore[no-untyped-def]
            await asyncio.sleep(0.001)
            if hasattr(request, "username") and not request.username:
                raise ValueError("Username cannot be empty")
            return await next()

    services = Services()
    services.add(AsyncValidationBehavior())
    services.add(AsyncCreateUserHandler())
    provider = services.provider()

    mediator = Mediator(provider)

    # Valid request should work
    response = await mediator.send(CreateUserRequest(username="alice"))
    assert response.username == "alice"

    # Invalid request should raise
    with pytest.raises(ValueError, match="Username cannot be empty"):
        await mediator.send(CreateUserRequest(username=""))


@pytest.mark.asyncio
async def test_async_mediator_behaviors_are_stateful() -> None:
    """Test async behaviors can maintain state across requests."""

    @dataclass
    class UserResponse:
        user_id: int
        username: str

    @dataclass
    class CreateUserRequest(Request[UserResponse]):
        username: str

    class AsyncCreateUserHandler(RequestHandler[CreateUserRequest]):
        async def __call__(self, request: CreateUserRequest) -> UserResponse:
            await asyncio.sleep(0.001)
            return UserResponse(user_id=1, username=request.username)

    class AsyncStatefulBehavior(PipelineBehavior[CreateUserRequest]):
        def __init__(self) -> None:
            self.call_count = 0

        async def __call__(self, request, next):  # type: ignore[no-untyped-def]
            self.call_count += 1
            await asyncio.sleep(0.001)
            return await next()

    services = Services()
    counter = AsyncStatefulBehavior()
    services.add(counter)
    services.add(AsyncCreateUserHandler())
    provider = services.provider()

    mediator = Mediator(provider)

    # Call multiple times
    await mediator.send(CreateUserRequest(username="alice"))
    await mediator.send(CreateUserRequest(username="bob"))
    await mediator.send(CreateUserRequest(username="charlie"))

    assert counter.call_count == 3


@pytest.mark.asyncio
async def test_async_mediator_behavior_exception_propagates() -> None:
    """Test exceptions from async behaviors propagate correctly."""

    @dataclass
    class UserResponse:
        user_id: int
        username: str

    @dataclass
    class CreateUserRequest(Request[UserResponse]):
        username: str

    class AsyncCreateUserHandler(RequestHandler[CreateUserRequest]):
        async def __call__(self, request: CreateUserRequest) -> UserResponse:
            await asyncio.sleep(0.001)
            return UserResponse(user_id=1, username=request.username)

    class AsyncExceptionBehavior(PipelineBehavior[CreateUserRequest]):
        async def __call__(self, request, next):  # type: ignore[no-untyped-def]
            raise RuntimeError("Async behavior error")

    services = Services()
    services.add(AsyncExceptionBehavior())
    services.add(AsyncCreateUserHandler())
    provider = services.provider()

    mediator = Mediator(provider)

    with pytest.raises(RuntimeError, match="Async behavior error"):
        await mediator.send(CreateUserRequest(username="alice"))


@pytest.mark.asyncio
async def test_async_mediator_behavior_can_wrap_handler_exception() -> None:
    """Test async behavior can catch and handle exceptions from handler."""

    @dataclass
    class UserResponse:
        user_id: int
        username: str

    @dataclass
    class FailingRequest(Request[UserResponse]):
        username: str

    class AsyncFailingHandler(RequestHandler[FailingRequest]):
        async def __call__(self, request: FailingRequest) -> UserResponse:
            raise ValueError("RequestHandler failed")

    class AsyncExceptionHandlingBehavior(PipelineBehavior[FailingRequest]):
        async def __call__(self, request, next):  # type: ignore[no-untyped-def]
            try:
                return await next()
            except ValueError:
                # Return fallback response
                return UserResponse(user_id=-1, username="error")

    services = Services()
    services.add(AsyncExceptionHandlingBehavior())
    services.add(AsyncFailingHandler())
    provider = services.provider()

    mediator = Mediator(provider)
    response = await mediator.send(FailingRequest(username="alice"))

    # Exception was caught and handled
    assert response.user_id == -1
    assert response.username == "error"


@pytest.mark.asyncio
async def test_async_mediator_concurrent_requests_with_behaviors() -> None:
    """Test async mediator can handle concurrent requests with behaviors."""

    @dataclass
    class UserResponse:
        user_id: int
        username: str

    @dataclass
    class CreateUserRequest(Request[UserResponse]):
        username: str

    class AsyncCreateUserHandler(RequestHandler[CreateUserRequest]):
        async def __call__(self, request: CreateUserRequest) -> UserResponse:
            await asyncio.sleep(0.001)
            return UserResponse(user_id=1, username=request.username)

    log: list[str] = []

    class AsyncLoggingBehavior(PipelineBehavior[CreateUserRequest]):
        async def __call__(self, request, next):  # type: ignore[no-untyped-def]
            log.append("logging:before")
            response = await next()
            log.append("logging:after")
            return response

    services = Services()
    services.add(AsyncLoggingBehavior())
    services.add(AsyncCreateUserHandler())
    provider = services.provider()

    mediator = Mediator(provider)

    # Execute multiple requests concurrently
    results = await asyncio.gather(
        mediator.send(CreateUserRequest(username="alice")),
        mediator.send(CreateUserRequest(username="bob")),
        mediator.send(CreateUserRequest(username="charlie")),
    )

    assert results[0].username == "alice"
    assert results[1].username == "bob"
    assert results[2].username == "charlie"

    # All requests should have been logged
    assert log.count("logging:before") == 3
    assert log.count("logging:after") == 3
