"""Tests for dataclass compatibility with PyMediate.

This module tests that pymediate works correctly with Python dataclasses,
focusing on pymediate-specific functionality rather than dataclass features.
"""

from dataclasses import dataclass

import pytest

from pymediate import Handler, Mediator, Request, SimpleResolver

# ========== Basic Dataclass Support ==========


@dataclass
class UserResponse:
    """Simple dataclass response."""

    user_id: int
    username: str
    email: str


@dataclass
class CreateUserRequest(Request[UserResponse]):
    """Dataclass request inheriting from Request[T].

    This is the recommended pattern for using dataclasses with PyMediate.
    """

    username: str
    email: str


class CreateUserHandler(Handler[CreateUserRequest]):
    def __init__(self) -> None:
        self.next_id = 1

    def __call__(self, request: CreateUserRequest) -> UserResponse:
        user_id = self.next_id
        self.next_id += 1
        return UserResponse(user_id=user_id, username=request.username, email=request.email)


def test_basic_dataclass_with_pymediate() -> None:
    """Test basic dataclass request and response with PyMediate.

    This is the recommended pattern:
    - Both request and response are pure dataclasses
    - Request inherits from Request[ResponseType]
    - Full type safety and IDE autocomplete support
    """
    handler = CreateUserHandler()
    resolver = SimpleResolver()
    resolver.register(handler)
    mediator = Mediator(resolver)

    request = CreateUserRequest(username="alice", email="alice@example.com")
    response = mediator.send(request)

    assert response.user_id == 1
    assert response.username == "alice"
    assert response.email == "alice@example.com"


# ========== Request Inheritance with Dataclasses ==========


@dataclass
class BaseResponse:
    """Base response class."""

    status: str


@dataclass
class ExtendedResponse(BaseResponse):
    """Extended response with additional fields."""

    data: str


@dataclass
class BaseRequest(Request[BaseResponse]):
    """Base request class."""

    action: str


@dataclass
class ExtendedRequest(Request[ExtendedResponse]):
    """Extended request - note: uses Request[T] directly, not BaseRequest."""

    action: str
    payload: str


class BaseHandler(Handler[BaseRequest]):
    def __call__(self, request: BaseRequest) -> BaseResponse:
        return BaseResponse(status="ok")


class ExtendedHandler(Handler[ExtendedRequest]):
    def __call__(self, request: ExtendedRequest) -> ExtendedResponse:
        return ExtendedResponse(status="ok", data=request.payload)


def test_dataclass_request_inheritance() -> None:
    """Test that dataclass requests can have inheritance hierarchies."""
    resolver = SimpleResolver()
    base_handler = BaseHandler()
    extended_handler = ExtendedHandler()

    resolver.register(base_handler)
    resolver.register(extended_handler)

    mediator = Mediator(resolver)

    base_response = mediator.send(BaseRequest(action="test"))
    assert base_response.status == "ok"

    extended_response = mediator.send(ExtendedRequest(action="test", payload="data"))
    assert extended_response.status == "ok"
    assert extended_response.data == "data"


# ========== Multiple Request Types with Same Response ==========


@dataclass
class StatusResponse:
    """Shared response type."""

    result: str


@dataclass
class RequestA(Request[StatusResponse]):
    """First request type."""

    value_a: str


@dataclass
class RequestB(Request[StatusResponse]):
    """Second request type."""

    value_b: int


class HandlerA(Handler[RequestA]):
    def __call__(self, request: RequestA) -> StatusResponse:
        return StatusResponse(result=f"A:{request.value_a}")


class HandlerB(Handler[RequestB]):
    def __call__(self, request: RequestB) -> StatusResponse:
        return StatusResponse(result=f"B:{request.value_b}")


def test_multiple_dataclass_requests_same_response() -> None:
    """Test that multiple request types can return the same response type."""
    resolver = SimpleResolver()
    resolver.register(HandlerA())
    resolver.register(HandlerB())
    mediator = Mediator(resolver)

    resp_a = mediator.send(RequestA(value_a="test"))
    resp_b = mediator.send(RequestB(value_b=42))

    assert resp_a.result == "A:test"
    assert resp_b.result == "B:42"


# ========== Mixin Support ==========


class TimestampMixin:
    """Mixin providing timestamp functionality."""

    def get_timestamp(self) -> str:
        return "2025-01-01T00:00:00Z"


@dataclass
class TimestampedResponse:
    """Response with timestamp."""

    value: int
    timestamp: str


@dataclass
class TimestampedRequest(TimestampMixin, Request[TimestampedResponse]):
    """Request with mixin and Request inheritance."""

    data: str


class TimestampedHandler(Handler[TimestampedRequest]):
    def __call__(self, request: TimestampedRequest) -> TimestampedResponse:
        return TimestampedResponse(value=len(request.data), timestamp=request.get_timestamp())


def test_dataclass_with_mixin() -> None:
    """Test that dataclasses can use mixins with Request inheritance."""
    resolver = SimpleResolver()
    resolver.register(TimestampedHandler())
    mediator = Mediator(resolver)

    request = TimestampedRequest(data="test")
    response = mediator.send(request)

    assert response.value == 4
    assert response.timestamp == "2025-01-01T00:00:00Z"


# ========== Dependency Injection Integration ==========


@pytest.mark.requires_di
def test_dataclass_with_dependency_injection() -> None:
    """Test dataclass requests and responses with dependency injection."""
    from dependency_injector import containers, providers

    from pymediate import DependencyInjectorResolver

    @dataclass
    class DIResponse:
        user_id: int
        username: str

    @dataclass
    class DIRequest(Request[DIResponse]):
        username: str
        email: str

    class Database:
        def __init__(self) -> None:
            self.next_id = 1

        def insert_user(self, username: str, email: str) -> int:
            user_id = self.next_id
            self.next_id += 1
            return user_id

    class DIHandler(Handler[DIRequest]):
        def __init__(self, database: Database):
            self.database = database

        def __call__(self, request: DIRequest) -> DIResponse:
            user_id = self.database.insert_user(request.username, request.email)
            return DIResponse(user_id=user_id, username=request.username)

    class DIContainer(containers.DeclarativeContainer):
        database = providers.Singleton(Database)
        user_handler = providers.Factory(DIHandler, database=database)

    container = DIContainer()
    resolver = DependencyInjectorResolver(container)
    mediator = Mediator(resolver)

    response = mediator.send(DIRequest(username="alice", email="alice@example.com"))
    assert response.user_id == 1
    assert response.username == "alice"


# ========== Empty Dataclasses ==========


@dataclass
class EmptyResponse:
    """Response with no fields."""

    pass


@dataclass
class EmptyRequest(Request[EmptyResponse]):
    """Request with no fields."""

    pass


class EmptyHandler(Handler[EmptyRequest]):
    def __call__(self, request: EmptyRequest) -> EmptyResponse:
        return EmptyResponse()


def test_empty_dataclasses() -> None:
    """Test that empty dataclasses work with PyMediate."""
    resolver = SimpleResolver()
    resolver.register(EmptyHandler())
    mediator = Mediator(resolver)

    response = mediator.send(EmptyRequest())
    assert isinstance(response, EmptyResponse)
