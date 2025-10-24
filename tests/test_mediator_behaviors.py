"""Tests for mediator integration with pipeline behaviors."""

from dataclasses import dataclass

import pytest

from pymediate import Handler, Mediator, PipelineBehaviorBase, Request, Services


def test_mediator_without_behaviors_calls_handler_directly() -> None:
    """Test that mediator without behaviors calls handler directly (fast path)."""

    @dataclass
    class UserResponse:
        user_id: int
        username: str

    @dataclass
    class CreateUserRequest(Request[UserResponse]):
        username: str

    class CreateUserHandler(Handler[CreateUserRequest]):
        def __call__(self, request: CreateUserRequest) -> UserResponse:
            return UserResponse(user_id=1, username=request.username)

    services = Services()
    services.add(CreateUserHandler())
    provider = services.provider()

    mediator = Mediator(provider)
    response = mediator.send(CreateUserRequest(username="alice"))

    assert response.user_id == 1
    assert response.username == "alice"


def test_mediator_with_single_behavior() -> None:
    """Test mediator with a single pipeline behavior."""

    @dataclass
    class UserResponse:
        user_id: int
        username: str

    @dataclass
    class CreateUserRequest(Request[UserResponse]):
        username: str

    class CreateUserHandler(Handler[CreateUserRequest]):
        def __call__(self, request: CreateUserRequest) -> UserResponse:
            return UserResponse(user_id=1, username=request.username)

    log: list[str] = []

    class LoggingBehavior(PipelineBehaviorBase):
        def __call__(self, request, next):  # type: ignore[no-untyped-def]
            log.append("logging:before")
            response = next()
            log.append("logging:after")
            return response

    services = Services()
    services.add(LoggingBehavior())
    services.add(CreateUserHandler())
    provider = services.provider()

    mediator = Mediator(provider)
    response = mediator.send(CreateUserRequest(username="alice"))

    assert response.user_id == 1
    assert response.username == "alice"
    assert log == ["logging:before", "logging:after"]


def test_mediator_with_multiple_behaviors_executes_in_order() -> None:
    """Test that multiple behaviors execute in registration order."""

    @dataclass
    class UserResponse:
        user_id: int
        username: str

    @dataclass
    class CreateUserRequest(Request[UserResponse]):
        username: str

    class CreateUserHandler(Handler[CreateUserRequest]):
        def __call__(self, request: CreateUserRequest) -> UserResponse:
            return UserResponse(user_id=1, username=request.username)

    log: list[str] = []

    class LoggingBehavior(PipelineBehaviorBase):
        def __call__(self, request, next):  # type: ignore[no-untyped-def]
            log.append("logging:before")
            response = next()
            log.append("logging:after")
            return response

    class TimingBehavior(PipelineBehaviorBase):
        def __call__(self, request, next):  # type: ignore[no-untyped-def]
            log.append("timing:before")
            response = next()
            log.append("timing:after")
            return response

    services = Services()
    services.add(LoggingBehavior())  # Registered first = outermost
    services.add(TimingBehavior())  # Registered second
    services.add(CreateUserHandler())
    provider = services.provider()

    mediator = Mediator(provider)
    response = mediator.send(CreateUserRequest(username="alice"))

    assert response.user_id == 1
    # Logging wraps timing
    assert log == [
        "logging:before",
        "timing:before",
        "timing:after",
        "logging:after",
    ]


def test_mediator_behaviors_can_modify_response() -> None:
    """Test that behaviors can modify the response."""

    @dataclass
    class UserResponse:
        user_id: int
        username: str

    @dataclass
    class CreateUserRequest(Request[UserResponse]):
        username: str

    class CreateUserHandler(Handler[CreateUserRequest]):
        def __call__(self, request: CreateUserRequest) -> UserResponse:
            return UserResponse(user_id=1, username=request.username)

    class ResponseModifyingBehavior(PipelineBehaviorBase):
        def __call__(self, request, next):  # type: ignore[no-untyped-def]
            response = next()
            response.username = response.username + "_modified"
            return response

    services = Services()
    services.add(ResponseModifyingBehavior())
    services.add(CreateUserHandler())
    provider = services.provider()

    mediator = Mediator(provider)
    response = mediator.send(CreateUserRequest(username="alice"))

    assert response.user_id == 1
    assert response.username == "alice_modified"


def test_mediator_behavior_can_short_circuit() -> None:
    """Test that behavior can short-circuit by not calling next."""

    @dataclass
    class UserResponse:
        user_id: int
        username: str

    @dataclass
    class CreateUserRequest(Request[UserResponse]):
        username: str

    class CreateUserHandler(Handler[CreateUserRequest]):
        def __call__(self, request: CreateUserRequest) -> UserResponse:
            return UserResponse(user_id=1, username=request.username)

    class ShortCircuitBehavior(PipelineBehaviorBase):
        def __call__(self, request, next):  # type: ignore[no-untyped-def]
            # Don't call next - return early
            return UserResponse(user_id=-1, username="short-circuited")

    services = Services()
    services.add(ShortCircuitBehavior())
    services.add(CreateUserHandler())
    provider = services.provider()

    mediator = Mediator(provider)
    response = mediator.send(CreateUserRequest(username="alice"))

    # Handler should not be called
    assert response.user_id == -1
    assert response.username == "short-circuited"


def test_mediator_validation_behavior() -> None:
    """Test validation behavior that can reject invalid requests."""

    @dataclass
    class UserResponse:
        user_id: int
        username: str

    @dataclass
    class CreateUserRequest(Request[UserResponse]):
        username: str

    class CreateUserHandler(Handler[CreateUserRequest]):
        def __call__(self, request: CreateUserRequest) -> UserResponse:
            return UserResponse(user_id=1, username=request.username)

    class ValidationBehavior(PipelineBehaviorBase):
        def __call__(self, request, next):  # type: ignore[no-untyped-def]
            if hasattr(request, "username") and not request.username:
                raise ValueError("Username cannot be empty")
            return next()

    services = Services()
    services.add(ValidationBehavior())
    services.add(CreateUserHandler())
    provider = services.provider()

    mediator = Mediator(provider)

    # Valid request should work
    response = mediator.send(CreateUserRequest(username="alice"))
    assert response.username == "alice"

    # Invalid request should raise
    with pytest.raises(ValueError, match="Username cannot be empty"):
        mediator.send(CreateUserRequest(username=""))


def test_mediator_behaviors_are_stateful() -> None:
    """Test that behaviors can maintain state across requests."""

    @dataclass
    class UserResponse:
        user_id: int
        username: str

    @dataclass
    class CreateUserRequest(Request[UserResponse]):
        username: str

    class CreateUserHandler(Handler[CreateUserRequest]):
        def __call__(self, request: CreateUserRequest) -> UserResponse:
            return UserResponse(user_id=1, username=request.username)

    class StatefulBehavior(PipelineBehaviorBase):
        def __init__(self) -> None:
            self.call_count = 0

        def __call__(self, request, next):  # type: ignore[no-untyped-def]
            self.call_count += 1
            return next()

    services = Services()
    counter = StatefulBehavior()
    services.add(counter)
    services.add(CreateUserHandler())
    provider = services.provider()

    mediator = Mediator(provider)

    # Call multiple times
    mediator.send(CreateUserRequest(username="alice"))
    mediator.send(CreateUserRequest(username="bob"))
    mediator.send(CreateUserRequest(username="charlie"))

    assert counter.call_count == 3


def test_mediator_behavior_exception_propagates() -> None:
    """Test that exceptions from behaviors propagate correctly."""

    @dataclass
    class UserResponse:
        user_id: int
        username: str

    @dataclass
    class CreateUserRequest(Request[UserResponse]):
        username: str

    class CreateUserHandler(Handler[CreateUserRequest]):
        def __call__(self, request: CreateUserRequest) -> UserResponse:
            return UserResponse(user_id=1, username=request.username)

    class ExceptionBehavior(PipelineBehaviorBase):
        def __call__(self, request, next):  # type: ignore[no-untyped-def]
            raise RuntimeError("Behavior error")

    services = Services()
    services.add(ExceptionBehavior())
    services.add(CreateUserHandler())
    provider = services.provider()

    mediator = Mediator(provider)

    with pytest.raises(RuntimeError, match="Behavior error"):
        mediator.send(CreateUserRequest(username="alice"))


def test_mediator_behavior_can_wrap_handler_exception() -> None:
    """Test that behavior can catch and handle exceptions from handler."""

    @dataclass
    class UserResponse:
        user_id: int
        username: str

    @dataclass
    class FailingRequest(Request[UserResponse]):
        username: str

    class FailingHandler(Handler[FailingRequest]):
        def __call__(self, request: FailingRequest) -> UserResponse:
            raise ValueError("Handler failed")

    class ExceptionHandlingBehavior(PipelineBehaviorBase):
        def __call__(self, request, next):  # type: ignore[no-untyped-def]
            try:
                return next()
            except ValueError:
                # Return fallback response
                return UserResponse(user_id=-1, username="error")

    services = Services()
    services.add(ExceptionHandlingBehavior())
    services.add(FailingHandler())
    provider = services.provider()

    mediator = Mediator(provider)
    response = mediator.send(FailingRequest(username="alice"))

    # Exception was caught and handled
    assert response.user_id == -1
    assert response.username == "error"


def test_mediator_registration_order_matters() -> None:
    """Test that behavior registration order determines execution order."""

    @dataclass
    class UserResponse:
        user_id: int
        username: str

    @dataclass
    class Request1(Request[UserResponse]):
        username: str

    @dataclass
    class Request2(Request[UserResponse]):
        username: str

    class Handler1(Handler[Request1]):
        def __call__(self, request: Request1) -> UserResponse:
            return UserResponse(user_id=1, username=request.username)

    class Handler2(Handler[Request2]):
        def __call__(self, request: Request2) -> UserResponse:
            return UserResponse(user_id=2, username=request.username)

    log: list[str] = []

    class LoggingBehavior(PipelineBehaviorBase):
        def __call__(self, request, next):  # type: ignore[no-untyped-def]
            log.append("logging:before")
            response = next()
            log.append("logging:after")
            return response

    class TimingBehavior(PipelineBehaviorBase):
        def __call__(self, request, next):  # type: ignore[no-untyped-def]
            log.append("timing:before")
            response = next()
            log.append("timing:after")
            return response

    # Order 1: Logging then Timing
    services1 = Services()
    services1.add(LoggingBehavior())
    services1.add(TimingBehavior())
    services1.add(Handler1())
    provider1 = services1.provider()

    mediator1 = Mediator(provider1)
    log.clear()
    mediator1.send(Request1(username="alice"))

    order1 = log.copy()

    # Order 2: Timing then Logging
    services2 = Services()
    services2.add(TimingBehavior())
    services2.add(LoggingBehavior())
    services2.add(Handler2())
    provider2 = services2.provider()

    mediator2 = Mediator(provider2)
    log.clear()
    mediator2.send(Request2(username="bob"))

    order2 = log.copy()

    # Orders should be different
    assert order1 == [
        "logging:before",
        "timing:before",
        "timing:after",
        "logging:after",
    ]
    assert order2 == [
        "timing:before",
        "logging:before",
        "logging:after",
        "timing:after",
    ]
