"""Tests for Mediator class."""

from typing import Any

import pytest

from pymediate.sync import HandlerNotFoundError, Mediator, Request, RequestHandler, Services


def test_mediator_creation() -> None:
    """Test that Mediator can be created with a resolver."""
    services = Services()
    provider = services.provider()
    mediator = Mediator(provider)
    assert mediator is not None


def test_mediator_send_request() -> None:
    """Test sending a request through mediator."""

    class GreetingResponse:
        def __init__(self, message: str):
            self.message = message

    class GreetingRequest(Request[GreetingResponse]):
        def __init__(self, name: str):
            self.name = name

    class GreetingHandler(RequestHandler[GreetingRequest]):
        def __call__(self, request: GreetingRequest) -> GreetingResponse:
            return GreetingResponse(f"Hello, {request.name}!")

    services = Services()
    services.add(GreetingHandler())
    provider = services.provider()
    mediator = Mediator(provider)

    request = GreetingRequest("Alice")
    response = mediator.send(request)

    assert isinstance(response, GreetingResponse)
    assert response.message == "Hello, Alice!"


def test_mediator_send_unregistered_request() -> None:
    """Test that sending unregistered request raises ValueError."""

    class UnhandledResp:
        pass

    class UnhandledReq(Request[UnhandledResp]):
        def __init__(self, data: str):
            self.data = data

    services = Services()
    provider = services.provider()
    mediator = Mediator(provider)

    with pytest.raises(HandlerNotFoundError):
        mediator.send(UnhandledReq("test"))


def test_mediator_with_multiple_handlers() -> None:
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

    class AddHandler(RequestHandler[AddRequest]):
        def __call__(self, request: AddRequest) -> AddResponse:
            return AddResponse(request.a + request.b)

    class MultiplyHandler(RequestHandler[MultiplyRequest]):
        def __call__(self, request: MultiplyRequest) -> MultiplyResponse:
            return MultiplyResponse(request.a * request.b)

    services = Services()
    services.add(AddHandler())
    services.add(MultiplyHandler())
    provider = services.provider()
    mediator = Mediator(provider)

    add_result = mediator.send(AddRequest(5, 3))
    mult_result = mediator.send(MultiplyRequest(5, 3))

    assert add_result.result == 8
    assert mult_result.result == 15


def test_mediator_preserves_request_data() -> None:
    """Test that mediator preserves original request data."""

    class EchoResponse:
        def __init__(self, data: dict[str, Any]):
            self.data = data

    class EchoRequest(Request[EchoResponse]):
        def __init__(self, data: dict[str, Any]):
            self.data = data

    class EchoHandler(RequestHandler[EchoRequest]):
        def __call__(self, request: EchoRequest) -> EchoResponse:
            return EchoResponse(request.data.copy())

    services = Services()
    services.add(EchoHandler())
    provider = services.provider()
    mediator = Mediator(provider)

    original_data = {"key": "value", "number": 42}
    request = EchoRequest(original_data)
    response = mediator.send(request)

    assert response.data == original_data
    assert response.data is not original_data  # Should be a copy


def test_mediator_with_stateful_handler() -> None:
    """Test mediator with a handler that maintains state."""

    class CountResponse:
        def __init__(self, count: int):
            self.count = count

    class CountRequest(Request[CountResponse]):
        pass

    class CounterHandler(RequestHandler[CountRequest]):
        def __init__(self) -> None:
            self.count = 0

        def __call__(self, request: CountRequest) -> CountResponse:
            self.count += 1
            return CountResponse(self.count)

    services = Services()
    handler = CounterHandler()
    services.add(handler)
    provider = services.provider()
    mediator = Mediator(provider)

    resp1 = mediator.send(CountRequest())
    resp2 = mediator.send(CountRequest())
    resp3 = mediator.send(CountRequest())

    assert resp1.count == 1
    assert resp2.count == 2
    assert resp3.count == 3


def test_mediator_with_complex_request_response() -> None:
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

    class CreateUserHandler(RequestHandler[CreateUserRequest]):
        def __init__(self) -> None:
            self.next_id = 1

        def __call__(self, request: CreateUserRequest) -> CreateUserResponse:
            user = User(self.next_id, request.name, request.email)
            self.next_id += 1
            return CreateUserResponse(
                user=user, success=True, message=f"User {user.name} created successfully"
            )

    services = Services()
    services.add(CreateUserHandler())
    provider = services.provider()
    mediator = Mediator(provider)

    request = CreateUserRequest("John Doe", "john@example.com")
    response = mediator.send(request)

    assert response.success is True
    assert response.user.id == 1
    assert response.user.name == "John Doe"
    assert response.user.email == "john@example.com"
    assert "created successfully" in response.message


def test_mediator_error_propagation() -> None:
    """Test that errors in handlers are propagated through mediator."""

    class ErrorResponse:
        pass

    class ErrorRequest(Request[ErrorResponse]):
        pass

    class ErrorHandler(RequestHandler[ErrorRequest]):
        def __call__(self, request: ErrorRequest) -> ErrorResponse:
            raise RuntimeError("RequestHandler error")

    services = Services()
    services.add(ErrorHandler())
    provider = services.provider()
    mediator = Mediator(provider)

    with pytest.raises(RuntimeError, match="RequestHandler error"):
        mediator.send(ErrorRequest())


def test_mediator_with_different_resolvers() -> None:
    """Test that different mediator instances can have different service providers."""

    class Resp:
        def __init__(self, value: int):
            self.value = value

    class Req(Request[Resp]):
        pass

    class ReqHandler(RequestHandler[Req]):
        def __init__(self, value: int):
            self.value = value

        def __call__(self, request: Req) -> Resp:
            return Resp(self.value)

    services1 = Services()
    services1.add(ReqHandler(1))
    provider1 = services1.provider()

    services2 = Services()
    services2.add(ReqHandler(2))
    provider2 = services2.provider()

    mediator1 = Mediator(provider1)
    mediator2 = Mediator(provider2)

    resp1 = mediator1.send(Req())
    resp2 = mediator2.send(Req())

    assert resp1.value == 1
    assert resp2.value == 2
