"""Tests for mediator integration with pipeline behaviors."""

from dataclasses import dataclass
from typing import Any

import pytest

from pymediate.sync import Mediator, PipelineBehavior, Request, RequestHandler, Services


def test_mediator_without_behaviors_calls_handler_directly() -> None:
    """Test that mediator without behaviors calls handler directly (fast path)."""

    @dataclass
    class UserResponse:
        user_id: int
        username: str

    @dataclass
    class CreateUserRequest(Request[UserResponse]):
        username: str

    class CreateUserHandler(RequestHandler[CreateUserRequest]):
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

    class CreateUserHandler(RequestHandler[CreateUserRequest]):
        def __call__(self, request: CreateUserRequest) -> UserResponse:
            return UserResponse(user_id=1, username=request.username)

    log: list[str] = []

    class LoggingBehavior(PipelineBehavior[CreateUserRequest]):
        def __call__(self, request, next):  # type: ignore[no-untyped-def]
            log.append("logging:before")
            response = next()
            log.append("logging:after")
            return response

    services = Services()
    services.add(LoggingBehavior())
    services.add(CreateUserHandler())
    provider = services.provider()

    mediator = Mediator(provider, behaviors=[LoggingBehavior])
    response = mediator.send(CreateUserRequest(username="alice"))

    assert response.user_id == 1
    assert response.username == "alice"
    assert log == ["logging:before", "logging:after"]


def test_mediator_with_multiple_behaviors_executes_in_declared_order() -> None:
    """Test that multiple behaviors execute in the order the behaviors= list declares."""

    @dataclass
    class UserResponse:
        user_id: int
        username: str

    @dataclass
    class CreateUserRequest(Request[UserResponse]):
        username: str

    class CreateUserHandler(RequestHandler[CreateUserRequest]):
        def __call__(self, request: CreateUserRequest) -> UserResponse:
            return UserResponse(user_id=1, username=request.username)

    log: list[str] = []

    class LoggingBehavior(PipelineBehavior[CreateUserRequest]):
        def __call__(self, request, next):  # type: ignore[no-untyped-def]
            log.append("logging:before")
            response = next()
            log.append("logging:after")
            return response

    class TimingBehavior(PipelineBehavior[CreateUserRequest]):
        def __call__(self, request, next):  # type: ignore[no-untyped-def]
            log.append("timing:before")
            response = next()
            log.append("timing:after")
            return response

    services = Services()
    services.add(LoggingBehavior())
    services.add(TimingBehavior())
    services.add(CreateUserHandler())
    provider = services.provider()

    mediator = Mediator(provider, behaviors=[LoggingBehavior, TimingBehavior])  # Logging outermost
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

    class CreateUserHandler(RequestHandler[CreateUserRequest]):
        def __call__(self, request: CreateUserRequest) -> UserResponse:
            return UserResponse(user_id=1, username=request.username)

    class ResponseModifyingBehavior(PipelineBehavior[CreateUserRequest]):
        def __call__(self, request, next):  # type: ignore[no-untyped-def]
            response = next()
            response.username = response.username + "_modified"
            return response

    services = Services()
    services.add(ResponseModifyingBehavior())
    services.add(CreateUserHandler())
    provider = services.provider()

    mediator = Mediator(provider, behaviors=[ResponseModifyingBehavior])
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

    class CreateUserHandler(RequestHandler[CreateUserRequest]):
        def __call__(self, request: CreateUserRequest) -> UserResponse:
            return UserResponse(user_id=1, username=request.username)

    class ShortCircuitBehavior(PipelineBehavior[CreateUserRequest]):
        def __call__(self, request, next):  # type: ignore[no-untyped-def]
            # Don't call next - return early
            return UserResponse(user_id=-1, username="short-circuited")

    services = Services()
    services.add(ShortCircuitBehavior())
    services.add(CreateUserHandler())
    provider = services.provider()

    mediator = Mediator(provider, behaviors=[ShortCircuitBehavior])
    response = mediator.send(CreateUserRequest(username="alice"))

    # RequestHandler should not be called
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

    class CreateUserHandler(RequestHandler[CreateUserRequest]):
        def __call__(self, request: CreateUserRequest) -> UserResponse:
            return UserResponse(user_id=1, username=request.username)

    class ValidationBehavior(PipelineBehavior[CreateUserRequest]):
        def __call__(self, request, next):  # type: ignore[no-untyped-def]
            if hasattr(request, "username") and not request.username:
                raise ValueError("Username cannot be empty")
            return next()

    services = Services()
    services.add(ValidationBehavior())
    services.add(CreateUserHandler())
    provider = services.provider()

    mediator = Mediator(provider, behaviors=[ValidationBehavior])

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

    class CreateUserHandler(RequestHandler[CreateUserRequest]):
        def __call__(self, request: CreateUserRequest) -> UserResponse:
            return UserResponse(user_id=1, username=request.username)

    class StatefulBehavior(PipelineBehavior[CreateUserRequest]):
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

    mediator = Mediator(provider, behaviors=[StatefulBehavior])

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

    class CreateUserHandler(RequestHandler[CreateUserRequest]):
        def __call__(self, request: CreateUserRequest) -> UserResponse:
            return UserResponse(user_id=1, username=request.username)

    class ExceptionBehavior(PipelineBehavior[CreateUserRequest]):
        def __call__(self, request, next):  # type: ignore[no-untyped-def]
            raise RuntimeError("Behavior error")

    services = Services()
    services.add(ExceptionBehavior())
    services.add(CreateUserHandler())
    provider = services.provider()

    mediator = Mediator(provider, behaviors=[ExceptionBehavior])

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

    class FailingHandler(RequestHandler[FailingRequest]):
        def __call__(self, request: FailingRequest) -> UserResponse:
            raise ValueError("RequestHandler failed")

    class ExceptionHandlingBehavior(PipelineBehavior[FailingRequest]):
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

    mediator = Mediator(provider, behaviors=[ExceptionHandlingBehavior])
    response = mediator.send(FailingRequest(username="alice"))

    # Exception was caught and handled
    assert response.user_id == -1
    assert response.username == "error"


def test_mediator_behaviors_order_follows_behaviors_list_not_registration() -> None:
    """Test that the behaviors= list, not registration order, determines execution order."""

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

    class Handler1(RequestHandler[Request1]):
        def __call__(self, request: Request1) -> UserResponse:
            return UserResponse(user_id=1, username=request.username)

    class Handler2(RequestHandler[Request2]):
        def __call__(self, request: Request2) -> UserResponse:
            return UserResponse(user_id=2, username=request.username)

    log: list[str] = []

    class LoggingBehavior(PipelineBehavior[Request[Any]]):
        def __call__(self, request, next):  # type: ignore[no-untyped-def]
            log.append("logging:before")
            response = next()
            log.append("logging:after")
            return response

    class TimingBehavior(PipelineBehavior[Request[Any]]):
        def __call__(self, request, next):  # type: ignore[no-untyped-def]
            log.append("timing:before")
            response = next()
            log.append("timing:after")
            return response

    # Both mediators register in the same order; only the behaviors= list differs.
    services1 = Services()
    services1.add(LoggingBehavior())
    services1.add(TimingBehavior())
    services1.add(Handler1())
    provider1 = services1.provider()

    mediator1 = Mediator(provider1, behaviors=[LoggingBehavior, TimingBehavior])
    log.clear()
    mediator1.send(Request1(username="alice"))

    order1 = log.copy()

    services2 = Services()
    services2.add(LoggingBehavior())
    services2.add(TimingBehavior())
    services2.add(Handler2())
    provider2 = services2.provider()

    mediator2 = Mediator(provider2, behaviors=[TimingBehavior, LoggingBehavior])
    log.clear()
    mediator2.send(Request2(username="bob"))

    order2 = log.copy()

    # Orders should be different, driven entirely by the behaviors= list.
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


def test_mediator_rejects_behavior_not_registered_with_provider() -> None:
    """Test that an unregistered class in behaviors= fails at construction."""
    from pymediate import InvalidPipelineBehaviorsError

    @dataclass
    class UserResponse:
        user_id: int
        username: str

    @dataclass
    class CreateUserRequest(Request[UserResponse]):
        username: str

    class CreateUserHandler(RequestHandler[CreateUserRequest]):
        def __call__(self, request: CreateUserRequest) -> UserResponse:
            return UserResponse(user_id=1, username=request.username)

    class UnregisteredBehavior(PipelineBehavior[CreateUserRequest]):
        def __call__(self, request, next):  # type: ignore[no-untyped-def]
            return next()

    services = Services()
    services.add(CreateUserHandler())
    provider = services.provider()

    with pytest.raises(InvalidPipelineBehaviorsError, match="not registered"):
        Mediator(provider, behaviors=[UnregisteredBehavior])


def test_mediator_rejects_behavior_entry_not_a_pipeline_behavior_subclass() -> None:
    """Test that a non-PipelineBehavior entry in behaviors= fails at construction."""
    from pymediate import InvalidPipelineBehaviorsError

    @dataclass
    class UserResponse:
        user_id: int
        username: str

    @dataclass
    class CreateUserRequest(Request[UserResponse]):
        username: str

    class CreateUserHandler(RequestHandler[CreateUserRequest]):
        def __call__(self, request: CreateUserRequest) -> UserResponse:
            return UserResponse(user_id=1, username=request.username)

    class NotABehavior:
        pass

    services = Services()
    services.add(CreateUserHandler())
    provider = services.provider()

    with pytest.raises(InvalidPipelineBehaviorsError, match="subclass"):
        Mediator(provider, behaviors=[NotABehavior])  # type: ignore[list-item]


def test_mediator_rejects_duplicate_behavior_in_behaviors_list() -> None:
    """Test that a behavior class listed twice in behaviors= fails at construction."""
    from pymediate import InvalidPipelineBehaviorsError

    @dataclass
    class UserResponse:
        user_id: int
        username: str

    @dataclass
    class CreateUserRequest(Request[UserResponse]):
        username: str

    class CreateUserHandler(RequestHandler[CreateUserRequest]):
        def __call__(self, request: CreateUserRequest) -> UserResponse:
            return UserResponse(user_id=1, username=request.username)

    class LoggingBehavior(PipelineBehavior[CreateUserRequest]):
        def __call__(self, request, next):  # type: ignore[no-untyped-def]
            return next()

    services = Services()
    services.add(LoggingBehavior())
    services.add(CreateUserHandler())
    provider = services.provider()

    with pytest.raises(InvalidPipelineBehaviorsError, match="more than once"):
        Mediator(provider, behaviors=[LoggingBehavior, LoggingBehavior])


def test_mediator_registered_but_unlisted_behavior_does_not_run() -> None:
    """Test that a registered behavior absent from behaviors= is not part of the pipeline."""

    @dataclass
    class UserResponse:
        user_id: int
        username: str

    @dataclass
    class CreateUserRequest(Request[UserResponse]):
        username: str

    class CreateUserHandler(RequestHandler[CreateUserRequest]):
        def __call__(self, request: CreateUserRequest) -> UserResponse:
            return UserResponse(user_id=1, username=request.username)

    log: list[str] = []

    class LoggingBehavior(PipelineBehavior[CreateUserRequest]):
        def __call__(self, request, next):  # type: ignore[no-untyped-def]
            log.append("logging")
            return next()

    services = Services()
    services.add(LoggingBehavior())  # registered...
    services.add(CreateUserHandler())
    provider = services.provider()

    mediator = Mediator(provider)  # ...but not listed in behaviors=
    mediator.send(CreateUserRequest(username="alice"))

    assert log == []
