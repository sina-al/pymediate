"""Tests for Resolver protocol and SimpleResolver implementation."""

import pytest

from pymediate import Handler, Request, SimpleResolver


def test_simple_resolver_creation():
    """Test that SimpleResolver can be created."""
    resolver = SimpleResolver()
    assert resolver is not None


def test_simple_resolver_with_initial_handlers():
    """Test SimpleResolver initialization with handlers dict."""

    class Resp:
        pass

    class Req(Request[Resp]):
        pass

    class ReqHandler(Handler[Req]):
        def __call__(self, request: Req) -> Resp:
            return Resp()

    handler = ReqHandler()
    resolver = SimpleResolver(handlers={Req: handler})

    resolved = resolver.resolve(Req)
    assert resolved is handler


def test_register_handler():
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
    resolver.register(MyReq, handler)

    resolved = resolver.resolve(MyReq)
    assert resolved is handler


def test_resolve_unregistered_request():
    """Test that resolving unregistered request raises ValueError."""

    class UnregisteredResp:
        pass

    class UnregisteredReq(Request[UnregisteredResp]):
        pass

    resolver = SimpleResolver()

    with pytest.raises(ValueError, match="No handler registered"):
        resolver.resolve(UnregisteredReq)


def test_register_multiple_handlers():
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

    resolver.register(Req1, h1)
    resolver.register(Req2, h2)

    assert resolver.resolve(Req1) is h1
    assert resolver.resolve(Req2) is h2


def test_register_overwrites_existing_handler():
    """Test that registering same request type overwrites previous handler."""

    class Resp:
        pass

    class Req(Request[Resp]):
        pass

    class Handler1(Handler[Req]):
        def __call__(self, request: Req) -> Resp:
            return Resp()

    class Handler2(Handler[Req]):
        def __call__(self, request: Req) -> Resp:
            return Resp()

    resolver = SimpleResolver()
    h1 = Handler1()
    h2 = Handler2()

    resolver.register(Req, h1)
    assert resolver.resolve(Req) is h1

    resolver.register(Req, h2)
    assert resolver.resolve(Req) is h2


def test_resolver_with_empty_handlers_dict():
    """Test that SimpleResolver works with empty initial handlers."""
    resolver = SimpleResolver(handlers={})

    class Resp:
        pass

    class Req(Request[Resp]):
        pass

    with pytest.raises(ValueError):
        resolver.resolve(Req)


def test_resolver_preserves_handler_state():
    """Test that resolver preserves handler instance state."""

    class CounterResp:
        def __init__(self, count: int):
            self.count = count

    class CounterReq(Request[CounterResp]):
        pass

    class StatefulHandler(Handler[CounterReq]):
        def __init__(self):
            self.call_count = 0

        def __call__(self, request: CounterReq) -> CounterResp:
            self.call_count += 1
            return CounterResp(self.call_count)

    resolver = SimpleResolver()
    handler = StatefulHandler()
    resolver.register(CounterReq, handler)

    # Get handler and call it
    h = resolver.resolve(CounterReq)
    resp1 = h(CounterReq())
    resp2 = h(CounterReq())

    assert resp1.count == 1
    assert resp2.count == 2
    assert handler.call_count == 2
