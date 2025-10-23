"""Tests for Resolver protocol and SimpleResolver implementation.

This module tests the core resolver functionality:
- Handler registration and resolution
- Type safety enforcement
- Multiple handlers and resolvers
- Error handling
"""

from dataclasses import dataclass
from typing import Any

import pytest

from pymediate import (
    Handler,
    HandlerNotFoundError,
    Mediator,
    Request,
    SimpleResolver,
)


# ========== Basic Functionality Tests ==========
def test_simple_resolver_creation() -> None:
    """Test that SimpleResolver can be created."""
    resolver = SimpleResolver()
    assert resolver is not None


def test_simple_resolver_with_initial_handlers() -> None:
    """Test SimpleResolver initialization with handlers list."""

    class Resp:
        pass

    class Req(Request[Resp]):
        pass

    class ReqHandler(Handler[Req]):
        def __call__(self, request: Req) -> Resp:
            return Resp()

    handler = ReqHandler()
    resolver = SimpleResolver(handlers=[handler])

    resolved = resolver.resolve(ReqHandler)
    assert resolved is handler


def test_resolver_with_empty_handlers_dict() -> None:
    """Test that SimpleResolver works with empty initial handlers."""
    resolver = SimpleResolver(handlers=[])

    class Resp:
        pass

    class Req(Request[Resp]):
        pass

    class ReqHandler(Handler[Req]):
        def __call__(self, request: Req) -> Resp:
            return Resp()

    with pytest.raises(HandlerNotFoundError):
        resolver.resolve(ReqHandler)


# ========== Registration and Resolution Tests ==========
def test_register_handler() -> None:
    """Test registering a handler."""

    class MyResp:
        pass

    class MyReq(Request[MyResp]):
        pass

    class MyHandler(Handler[MyReq]):
        def __call__(self, request: MyReq) -> MyResp:
            return MyResp()

    resolver = SimpleResolver()
    handler = MyHandler()
    resolver.register(handler)

    resolved = resolver.resolve(MyHandler)
    assert resolved is handler


def test_resolve_unregistered_request() -> None:
    """Test that resolving unregistered handler raises HandlerNotFoundError."""

    class UnregisteredResp:
        pass

    class UnregisteredReq(Request[UnregisteredResp]):
        pass

    class UnregisteredHandler(Handler[UnregisteredReq]):
        def __call__(self, request: UnregisteredReq) -> UnregisteredResp:
            return UnregisteredResp()

    resolver = SimpleResolver()

    with pytest.raises(HandlerNotFoundError):
        resolver.resolve(UnregisteredHandler)


def test_register_multiple_handlers() -> None:
    """Test registering multiple handlers for different requests."""

    class Resp1:
        def __init__(self, x: int):
            self.x = x

    class Resp2:
        def __init__(self, y: str):
            self.y = y

    class Req1(Request[Resp1]):
        pass

    class Req2(Request[Resp2]):
        pass

    class Handler1(Handler[Req1]):
        def __call__(self, request: Req1) -> Resp1:
            return Resp1(1)

    class Handler2(Handler[Req2]):
        def __call__(self, request: Req2) -> Resp2:
            return Resp2("test")

    resolver = SimpleResolver()
    h1 = Handler1()
    h2 = Handler2()

    resolver.register(h1)
    resolver.register(h2)

    assert resolver.resolve(Handler1) is h1
    assert resolver.resolve(Handler2) is h2


def test_register_overwrites_existing_handler() -> None:
    """Test that registering same handler type overwrites previous handler."""

    class Resp:
        pass

    class Req(Request[Resp]):
        pass

    class ReqHandler(Handler[Req]):
        def __call__(self, request: Req) -> Resp:
            return Resp()

    resolver = SimpleResolver()
    h1 = ReqHandler()
    h2 = ReqHandler()

    resolver.register(h1)
    assert resolver.resolve(ReqHandler) is h1

    resolver.register(h2)
    assert resolver.resolve(ReqHandler) is h2


def test_resolver_preserves_handler_state() -> None:
    """Test that resolver preserves handler instance state."""

    class CounterResp:
        def __init__(self, count: int):
            self.count = count

    class CounterReq(Request[CounterResp]):
        pass

    class StatefulHandler(Handler[CounterReq]):
        def __init__(self) -> None:
            self.call_count = 0

        def __call__(self, request: CounterReq) -> CounterResp:
            self.call_count += 1
            return CounterResp(self.call_count)

    resolver = SimpleResolver()
    handler = StatefulHandler()
    resolver.register(handler)

    # Get handler and call it
    h = resolver.resolve(StatefulHandler)
    resp1 = h(CounterReq())
    resp2 = h(CounterReq())

    assert resp1.count == 1
    assert resp2.count == 2
    assert handler.call_count == 2


# ========== Type Safety Tests ==========
@dataclass
class TypeSafeResponse1:
    value: int


@dataclass
class TypeSafeResponse2:
    text: str


@dataclass
class TypeSafeRequest1(Request[TypeSafeResponse1]):
    data: str


@dataclass
class TypeSafeRequest2(Request[TypeSafeResponse2]):
    number: int


class TypeSafeHandler1(Handler[TypeSafeRequest1]):
    def __call__(self, request: TypeSafeRequest1) -> TypeSafeResponse1:
        return TypeSafeResponse1(value=len(request.data))


class TypeSafeHandler2(Handler[TypeSafeRequest2]):
    def __call__(self, request: TypeSafeRequest2) -> TypeSafeResponse2:
        return TypeSafeResponse2(text=str(request.number))


def test_type_safe_registration() -> None:
    """Test that SimpleResolver stores handler instances correctly."""
    resolver = SimpleResolver()

    # This should work - register handler instance
    handler1 = TypeSafeHandler1()
    resolver.register(handler1)

    resolved = resolver.resolve(TypeSafeHandler1)
    assert resolved is handler1


def test_type_mismatch_detection() -> None:
    """Test that SimpleResolver can store handlers independently."""
    resolver = SimpleResolver()

    # Register handler instance - new API doesn't validate at registration
    handler1 = TypeSafeHandler1()
    resolver.register(handler1)

    # Verify correct handler is resolved
    resolved = resolver.resolve(TypeSafeHandler1)
    assert resolved is handler1


def test_multiple_handlers_type_safety() -> None:
    """Test multiple handlers registered correctly."""
    resolver = SimpleResolver()

    handler1 = TypeSafeHandler1()
    handler2 = TypeSafeHandler2()

    resolver.register(handler1)
    resolver.register(handler2)

    # Verify correct handlers are resolved
    assert resolver.resolve(TypeSafeHandler1) is handler1
    assert resolver.resolve(TypeSafeHandler2) is handler2


def test_initial_handlers_dict_validation() -> None:
    """Test that handlers passed to __init__ are registered correctly."""
    handler1 = TypeSafeHandler1()

    # This should work
    resolver = SimpleResolver(handlers=[handler1])
    assert resolver.resolve(TypeSafeHandler1) is handler1

    # Multiple handlers should work
    handler2 = TypeSafeHandler2()
    resolver2 = SimpleResolver(handlers=[handler1, handler2])
    assert resolver2.resolve(TypeSafeHandler1) is handler1
    assert resolver2.resolve(TypeSafeHandler2) is handler2


def test_handler_replacement_type_safety() -> None:
    """Test that replacing handlers works correctly."""
    resolver = SimpleResolver()

    handler1a = TypeSafeHandler1()
    handler1b = TypeSafeHandler1()

    resolver.register(handler1a)
    assert resolver.resolve(TypeSafeHandler1) is handler1a

    # Replace with another instance of same handler type
    resolver.register(handler1b)
    assert resolver.resolve(TypeSafeHandler1) is handler1b


# ========== Multiple Resolvers Tests ==========
def test_multiple_resolvers_independence() -> None:
    """Test that multiple resolver instances are independent."""
    resolver1 = SimpleResolver()
    resolver2 = SimpleResolver()

    handler1a = TypeSafeHandler1()
    handler1b = TypeSafeHandler1()

    resolver1.register(handler1a)
    resolver2.register(handler1b)

    assert resolver1.resolve(TypeSafeHandler1) is handler1a
    assert resolver2.resolve(TypeSafeHandler1) is handler1b
    assert resolver1.resolve(TypeSafeHandler1) is not resolver2.resolve(TypeSafeHandler1)


# ========== Integration with Mediator ==========
def test_resolver_with_mediator() -> None:
    """Test resolver integration with Mediator."""

    @dataclass
    class MediatorTestUserCreatedResponse:
        user_id: int
        username: str

    @dataclass
    class MediatorTestCreateUserRequest(Request[MediatorTestUserCreatedResponse]):
        username: str
        email: str

    class MediatorTestCreateUserHandler(Handler[MediatorTestCreateUserRequest]):
        def __init__(self) -> None:
            self.next_id = 1

        def __call__(
            self, request: MediatorTestCreateUserRequest
        ) -> MediatorTestUserCreatedResponse:
            user_id = self.next_id
            self.next_id += 1
            return MediatorTestUserCreatedResponse(user_id=user_id, username=request.username)

    resolver = SimpleResolver()
    handler = MediatorTestCreateUserHandler()

    resolver.register(handler)

    mediator = Mediator(resolver)
    response = mediator.send(
        MediatorTestCreateUserRequest(username="alice", email="alice@example.com")
    )

    assert response.user_id == 1
    assert response.username == "alice"


# ========== Edge Cases ==========
def test_resolver_handles_untyped_handler_gracefully() -> None:
    """Test that resolver can store any handler instance."""
    resolver = SimpleResolver()

    # Create a mock handler without proper type metadata
    class UntypedHandler:
        def __call__(self, request: Any) -> str:
            return "result"

    # Should be able to register
    handler = UntypedHandler()
    resolver.register(handler)

    # Should resolve
    resolved = resolver.resolve(UntypedHandler)
    assert resolved == handler  # type: ignore[comparison-overlap]
