"""Tests for Mediator class."""

import pytest

from pymediate import Handler, Mediator, Request, SimpleResolver


def test_mediator_creation():
    """Test that Mediator can be created with a resolver."""
    resolver = SimpleResolver()
    mediator = Mediator(resolver)
    assert mediator is not None


def test_mediator_send_request():
    """Test sending a request through mediator."""

    class GreetingResponse:
        def __init__(self, message: str):
            self.message = message

    class GreetingRequest(Request[GreetingResponse]):
        def __init__(self, name: str):
            self.name = name

    class GreetingHandler(Handler[GreetingRequest]):
        def __call__(self, request: GreetingRequest) -> GreetingResponse:
            return GreetingResponse(f"Hello, {request.name}!")

    resolver = SimpleResolver()
    resolver.register(GreetingRequest, GreetingHandler())
    mediator = Mediator(resolver)

    request = GreetingRequest("Alice")
    response = mediator.send(request)

    assert isinstance(response, GreetingResponse)
    assert response.message == "Hello, Alice!"


def test_mediator_send_unregistered_request():
    """Test that sending unregistered request raises ValueError."""

    class UnhandledResp:
        pass

    class UnhandledReq(Request[UnhandledResp]):
        def __init__(self, data: str):
            self.data = data

    resolver = SimpleResolver()
    mediator = Mediator(resolver)

    with pytest.raises(ValueError, match="No handler registered"):
        mediator.send(UnhandledReq("test"))


def test_mediator_with_multiple_handlers():
    """Test mediator with multiple request/handler pairs."""

    class AddResponse:
        def __init__(self, result: int):
            self.result = result

    class MultiplyResponse:
        def __init__(self, result: int):
            self.result = result

    class AddRequest(Request[AddResponse]):
        def __init__(self, a: int, b: int):
            self.a = a
            self.b = b

    class MultiplyRequest(Request[MultiplyResponse]):
        def __init__(self, a: int, b: int):
            self.a = a
            self.b = b

    class AddHandler(Handler[AddRequest]):
        def __call__(self, request: AddRequest) -> AddResponse:
            return AddResponse(request.a + request.b)

    class MultiplyHandler(Handler[MultiplyRequest]):
        def __call__(self, request: MultiplyRequest) -> MultiplyResponse:
            return MultiplyResponse(request.a * request.b)

    resolver = SimpleResolver()
    resolver.register(AddRequest, AddHandler())
    resolver.register(MultiplyRequest, MultiplyHandler())
    mediator = Mediator(resolver)

    add_result = mediator.send(AddRequest(5, 3))
    mult_result = mediator.send(MultiplyRequest(5, 3))

    assert add_result.result == 8
    assert mult_result.result == 15


def test_mediator_preserves_request_data():
    """Test that mediator preserves original request data."""

    class EchoResponse:
        def __init__(self, data: dict):
            self.data = data

    class EchoRequest(Request[EchoResponse]):
        def __init__(self, data: dict):
            self.data = data

    class EchoHandler(Handler[EchoRequest]):
        def __call__(self, request: EchoRequest) -> EchoResponse:
            return EchoResponse(request.data.copy())

    resolver = SimpleResolver()
    resolver.register(EchoRequest, EchoHandler())
    mediator = Mediator(resolver)

    original_data = {"key": "value", "number": 42}
    request = EchoRequest(original_data)
    response = mediator.send(request)

    assert response.data == original_data
    assert response.data is not original_data  # Should be a copy


def test_mediator_with_stateful_handler():
    """Test mediator with a handler that maintains state."""

    class CountResponse:
        def __init__(self, count: int):
            self.count = count

    class CountRequest(Request[CountResponse]):
        pass

    class CounterHandler(Handler[CountRequest]):
        def __init__(self):
            self.count = 0

        def __call__(self, request: CountRequest) -> CountResponse:
            self.count += 1
            return CountResponse(self.count)

    resolver = SimpleResolver()
    handler = CounterHandler()
    resolver.register(CountRequest, handler)
    mediator = Mediator(resolver)

    resp1 = mediator.send(CountRequest())
    resp2 = mediator.send(CountRequest())
    resp3 = mediator.send(CountRequest())

    assert resp1.count == 1
    assert resp2.count == 2
    assert resp3.count == 3


def test_mediator_with_complex_request_response():
    """Test mediator with complex request and response objects."""

    class User:
        def __init__(self, id: int, name: str, email: str):
            self.id = id
            self.name = name
            self.email = email

    class CreateUserResponse:
        def __init__(self, user: User, success: bool, message: str):
            self.user = user
            self.success = success
            self.message = message

    class CreateUserRequest(Request[CreateUserResponse]):
        def __init__(self, name: str, email: str):
            self.name = name
            self.email = email

    class CreateUserHandler(Handler[CreateUserRequest]):
        def __init__(self):
            self.next_id = 1

        def __call__(self, request: CreateUserRequest) -> CreateUserResponse:
            user = User(self.next_id, request.name, request.email)
            self.next_id += 1
            return CreateUserResponse(
                user=user, success=True, message=f"User {user.name} created successfully"
            )

    resolver = SimpleResolver()
    resolver.register(CreateUserRequest, CreateUserHandler())
    mediator = Mediator(resolver)

    request = CreateUserRequest("John Doe", "john@example.com")
    response = mediator.send(request)

    assert response.success is True
    assert response.user.id == 1
    assert response.user.name == "John Doe"
    assert response.user.email == "john@example.com"
    assert "created successfully" in response.message


def test_mediator_error_propagation():
    """Test that errors in handlers are propagated through mediator."""

    class ErrorResponse:
        pass

    class ErrorRequest(Request[ErrorResponse]):
        pass

    class ErrorHandler(Handler[ErrorRequest]):
        def __call__(self, request: ErrorRequest) -> ErrorResponse:
            raise RuntimeError("Handler error")

    resolver = SimpleResolver()
    resolver.register(ErrorRequest, ErrorHandler())
    mediator = Mediator(resolver)

    with pytest.raises(RuntimeError, match="Handler error"):
        mediator.send(ErrorRequest())


def test_mediator_with_different_resolvers():
    """Test that different mediator instances can have different resolvers."""

    class Resp:
        def __init__(self, value: int):
            self.value = value

    class Req(Request[Resp]):
        pass

    class Handler1(Handler[Req]):
        def __call__(self, request: Req) -> Resp:
            return Resp(1)

    class Handler2(Handler[Req]):
        def __call__(self, request: Req) -> Resp:
            return Resp(2)

    resolver1 = SimpleResolver()
    resolver1.register(Req, Handler1())

    resolver2 = SimpleResolver()
    resolver2.register(Req, Handler2())

    mediator1 = Mediator(resolver1)
    mediator2 = Mediator(resolver2)

    resp1 = mediator1.send(Req())
    resp2 = mediator2.send(Req())

    assert resp1.value == 1
    assert resp2.value == 2
