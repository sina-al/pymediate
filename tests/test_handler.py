"""Tests for Handler class and metaclass."""

import pytest

from pymediate import (
    Handler,
    HandlerNotFoundError,
    InvalidHandlerSignatureError,
    InvalidRequestTypeError,
    Request,
    ResponseTypeMismatchError,
)
from pymediate._internal.registry import get_handler_class, has_handler


def test_handler_extracts_request_type() -> None:
    """Test that Handler metaclass extracts request type from generic."""

    class TestResponse:
        def __init__(self, value: int):
            self.value = value

    class TestRequest(Request[TestResponse]):
        def __init__(self, data: str):
            self.data = data

    class TestHandler(Handler[TestRequest]):
        def __call__(self, request: TestRequest) -> TestResponse:
            return TestResponse(42)

    assert TestHandler._request_type == TestRequest
    assert TestHandler._response_type == TestResponse


def test_handler_registration() -> None:
    """Test that Handler is registered in handler registry."""

    class Response:
        pass

    class Req(Request[Response]):
        pass

    class ReqHandler(Handler[Req]):
        def __call__(self, request: Req) -> Response:
            return Response()

    assert has_handler(Req)
    assert get_handler_class(Req) == ReqHandler


def test_handler_validates_correct_return_type() -> None:
    """Test that Handler with correct return type is accepted."""

    class GoodResponse:
        def __init__(self, msg: str):
            self.msg = msg

    class GoodRequest(Request[GoodResponse]):
        pass

    # This should not raise
    class GoodHandler(Handler[GoodRequest]):
        def __call__(self, request: GoodRequest) -> GoodResponse:
            return GoodResponse("ok")

    assert GoodHandler._response_type == GoodResponse


def test_handler_rejects_wrong_return_type() -> None:
    """Test that Handler with wrong return type is rejected."""

    class CorrectResponse:
        pass

    class WrongResponse:
        pass

    class ReqWithCorrectResponse(Request[CorrectResponse]):
        pass

    # This should raise ResponseTypeMismatchError
    with pytest.raises(ResponseTypeMismatchError):

        class BadHandler(Handler[ReqWithCorrectResponse]):
            def __call__(self, request: ReqWithCorrectResponse) -> WrongResponse:
                return WrongResponse()


def test_handler_rejects_wrong_parameter_type() -> None:
    """Test that Handler with wrong parameter type is rejected."""

    class Resp:
        pass

    class CorrectReq(Request[Resp]):
        pass

    class WrongReq(Request[Resp]):
        pass

    with pytest.raises(InvalidHandlerSignatureError):

        class BadHandler(Handler[CorrectReq]):
            def __call__(self, request: WrongReq) -> Resp:
                return Resp()


def test_handler_rejects_base_class_parameter_annotation() -> None:
    """Test that annotating a base class of the declared request type is rejected.

    Static checkers allow the broader annotation (contravariance), so the runtime
    error must teach the exact-annotation rule explicitly (ADR 0004).
    """

    class Resp:
        pass

    class BaseReq(Request[Resp]):
        pass

    class DerivedReq(BaseReq):
        pass

    with pytest.raises(InvalidHandlerSignatureError, match="a base class of DerivedReq"):

        class BadHandler(Handler[DerivedReq]):
            def __call__(self, request: BaseReq) -> Resp:
                return Resp()


def test_handler_rejects_union_parameter_annotation() -> None:
    """Test that a union annotation is rejected even when it includes the request type."""

    class Resp:
        pass

    class ReqA(Request[Resp]):
        pass

    class ReqB(Request[Resp]):
        pass

    with pytest.raises(InvalidHandlerSignatureError, match="exact request class"):

        class BadHandler(Handler[ReqA]):
            def __call__(self, request: ReqA | ReqB) -> Resp:
                return Resp()


def test_handler_requires_exactly_one_parameter() -> None:
    """Test that Handler __call__ must have exactly one parameter besides self."""

    class Resp:
        pass

    class Req(Request[Resp]):
        pass

    with pytest.raises(InvalidHandlerSignatureError):

        class TooManyParams(Handler[Req]):
            def __call__(self, request: Req, extra: str) -> Resp:
                return Resp()


def test_handler_requires_call_method() -> None:
    """Test that a Handler subclass without a __call__ override is rejected."""

    class Resp:
        pass

    class Req(Request[Resp]):
        pass

    with pytest.raises(InvalidHandlerSignatureError, match="must implement __call__"):

        class NoCallHandler(Handler[Req]):
            pass


def test_handler_requires_request_parameter_annotation() -> None:
    """Test that Handler __call__'s request parameter must have a type annotation."""

    class Resp:
        pass

    class Req(Request[Resp]):
        pass

    with pytest.raises(InvalidHandlerSignatureError, match="type annotation"):

        class UnannotatedParamHandler(Handler[Req]):
            def __call__(self, request) -> Resp:  # type: ignore[no-untyped-def]
                return Resp()


def test_handler_requires_return_type_annotation() -> None:
    """Test that Handler __call__ must have a return type annotation."""

    class Resp:
        pass

    class Req(Request[Resp]):
        pass

    with pytest.raises(InvalidHandlerSignatureError, match="return type annotation"):

        class UnannotatedReturnHandler(Handler[Req]):
            def __call__(self, request: Req):  # type: ignore[no-untyped-def]
                return Resp()


def test_handler_with_request_not_in_registry() -> None:
    """Test that Handler with unregistered request type raises error."""

    class UnregisteredRequest:
        """Not a Request subclass"""

        pass

    with pytest.raises(InvalidRequestTypeError):

        class BadHandler(Handler[UnregisteredRequest]):
            def __call__(self, request: UnregisteredRequest) -> None:
                pass


def test_handler_call() -> None:
    """Test that handler can be called."""

    class NumResponse:
        def __init__(self, result: int):
            self.result = result

    class NumRequest(Request[NumResponse]):
        def __init__(self, value: int):
            self.value = value

    class DoubleHandler(Handler[NumRequest]):
        def __call__(self, request: NumRequest) -> NumResponse:
            return NumResponse(request.value * 2)

    handler = DoubleHandler()
    request = NumRequest(21)
    response = handler(request)

    assert isinstance(response, NumResponse)
    assert response.result == 42


def test_get_request_type() -> None:
    """Test Handler.get_request_type() method."""

    class Resp:
        pass

    class Req(Request[Resp]):
        pass

    class TestHandler(Handler[Req]):
        def __call__(self, request: Req) -> Resp:
            return Resp()

    assert TestHandler.get_request_type() == Req


def test_get_response_type() -> None:
    """Test Handler.get_response_type() method."""

    class MyResp:
        pass

    class MyReq(Request[MyResp]):
        pass

    class TestHandler(Handler[MyReq]):
        def __call__(self, request: MyReq) -> MyResp:
            return MyResp()

    assert TestHandler.get_response_type() == MyResp


def test_get_handler_for_request() -> None:
    """Test Handler.get_handler_for_request() class method."""

    class Resp:
        pass

    class Req(Request[Resp]):
        pass

    class ReqHandler(Handler[Req]):
        def __call__(self, request: Req) -> Resp:
            return Resp()

    handler_class = Handler.get_handler_for_request(Req)
    assert handler_class == ReqHandler


def test_get_handler_for_unregistered_request() -> None:
    """Test that get_handler_for_request raises for unregistered request."""

    class UnhandledResp:
        pass

    class UnhandledReq(Request[UnhandledResp]):
        pass

    # Don't create a handler for it

    with pytest.raises(HandlerNotFoundError):
        Handler.get_handler_for_request(UnhandledReq)


def test_get_handler_for_unregistered_request_lists_available_handlers() -> None:
    """HandlerNotFoundError's message includes other registered request types, if any."""

    class RegisteredResp:
        pass

    class RegisteredReq(Request[RegisteredResp]):
        pass

    class RegisteredHandler(Handler[RegisteredReq]):
        def __call__(self, request: RegisteredReq) -> RegisteredResp:
            return RegisteredResp()

    class UnhandledResp:
        pass

    class UnhandledReq(Request[UnhandledResp]):
        pass

    with pytest.raises(HandlerNotFoundError) as exc_info:
        Handler.get_handler_for_request(UnhandledReq)

    assert exc_info.value.available_handlers == [RegisteredReq]
    assert "RegisteredReq" in str(exc_info.value)


def test_get_handler_for_unregistered_request_truncates_many_available_handlers() -> None:
    """HandlerNotFoundError truncates the available-handlers list beyond 5, with a count."""

    class Resp:
        pass

    for _ in range(6):

        class RegisteredReq(Request[Resp]):
            pass

        class RegisteredHandler(Handler[RegisteredReq]):
            def __call__(self, request: RegisteredReq) -> Resp:
                return Resp()

    class UnhandledReq(Request[Resp]):
        pass

    with pytest.raises(HandlerNotFoundError) as exc_info:
        Handler.get_handler_for_request(UnhandledReq)

    assert len(exc_info.value.available_handlers) == 6
    assert "... and 1 more" in str(exc_info.value)


def test_multiple_handlers_for_different_requests() -> None:
    """Test that multiple handlers can coexist."""

    class Resp1:
        def __init__(self, val: int):
            self.val = val

    class Resp2:
        def __init__(self, msg: str):
            self.msg = msg

    class Req1(Request[Resp1]):
        def __init__(self, x: int):
            self.x = x

    class Req2(Request[Resp2]):
        def __init__(self, text: str):
            self.text = text

    class Handler1(Handler[Req1]):
        def __call__(self, request: Req1) -> Resp1:
            return Resp1(request.x + 1)

    class Handler2(Handler[Req2]):
        def __call__(self, request: Req2) -> Resp2:
            return Resp2(request.text.upper())

    h1 = Handler1()
    h2 = Handler2()

    r1 = h1(Req1(10))
    r2 = h2(Req2("hello"))

    assert r1.val == 11
    assert r2.msg == "HELLO"
