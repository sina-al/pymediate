"""Tests for Request class and registration.

Following pytest best practices by using functions instead of test classes.
"""

from pymediate import Request
from pymediate.registry import get_all_request_types, get_response_type, has_response_type


def test_request_registration():
    """Test that Request subclass is registered with response type."""

    class TestResponse:
        def __init__(self, value: int):
            self.value = value

    class TestRequest(Request[TestResponse]):
        def __init__(self, data: str):
            self.data = data

    # Verify registration
    assert has_response_type(TestRequest)
    assert get_response_type(TestRequest) == TestResponse


def test_request_without_response_type():
    """Test that Request subclass without response type is not registered."""
    initial_registry_size = len(get_all_request_types())

    # This should work but not register a response type
    class TestRequestNoResponse(Request):
        pass

    # Should not be registered (no type parameter)
    assert not has_response_type(TestRequestNoResponse)
    assert len(get_all_request_types()) == initial_registry_size


def test_multiple_requests_with_different_responses():
    """Test multiple request types with different response types."""

    class Response1:
        pass

    class Response2:
        pass

    class Request1(Request[Response1]):
        pass

    class Request2(Request[Response2]):
        pass

    assert get_response_type(Request1) == Response1
    assert get_response_type(Request2) == Response2


def test_request_with_same_response_type():
    """Test multiple requests can share the same response type."""

    class SharedResponse:
        def __init__(self, status: str):
            self.status = status

    class Request1(Request[SharedResponse]):
        pass

    class Request2(Request[SharedResponse]):
        pass

    assert get_response_type(Request1) == SharedResponse
    assert get_response_type(Request2) == SharedResponse


def test_request_inheritance():
    """Test that Request subclass inheritance works correctly."""

    class BaseResponse:
        pass

    class BaseRequest(Request[BaseResponse]):
        pass

    class DerivedRequest(BaseRequest):
        pass

    # Base request should be registered
    assert has_response_type(BaseRequest)
    # Derived request inherits but doesn't create new registry entry
    # (it doesn't have its own type parameter)


def test_request_instantiation():
    """Test that Request subclass can be instantiated."""

    class MyResponse:
        def __init__(self, result: str):
            self.result = result

    class MyRequest(Request[MyResponse]):
        def __init__(self, data: str):
            self.data = data

    request = MyRequest("test_data")
    assert request.data == "test_data"


def test_request_attributes():
    """Test that Request can have multiple attributes."""

    class ComplexResponse:
        pass

    class ComplexRequest(Request[ComplexResponse]):
        def __init__(self, name: str, age: int, email: str):
            self.name = name
            self.age = age
            self.email = email

    request = ComplexRequest("John", 30, "john@example.com")
    assert request.name == "John"
    assert request.age == 30
    assert request.email == "john@example.com"
