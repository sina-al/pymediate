"""Tests for the registry module.

Tests the thread-safe registry API for managing request-response
and request-handler mappings.
"""

import threading
from typing import Any

from pymediate._internal.registry import (
    clear_all_registries,
    get_all_handler_request_types,
    get_all_request_types,
    get_handler_class,
    get_registry_stats,
    get_response_type,
    has_handler,
    has_response_type,
    register_request_response_type,
)
from pymediate.sync import Request, RequestHandler

# ========== Request Registry Tests ==========


def test_register_and_get_response_type() -> None:
    """Test registering and retrieving response types."""

    class MyResponse:
        pass

    class MyRequest(Request[MyResponse]):
        pass

    # Request should be auto-registered
    assert has_response_type(MyRequest)
    assert get_response_type(MyRequest) == MyResponse


def test_has_response_type() -> None:
    """Test checking if request type has a registered response."""

    class RegisteredResponse:
        pass

    class RegisteredRequest(Request[RegisteredResponse]):
        pass

    class UnregisteredRequest:
        pass

    assert has_response_type(RegisteredRequest)
    assert not has_response_type(UnregisteredRequest)


def test_get_response_type_returns_none_for_unregistered() -> None:
    """Test that getting unregistered response type returns None."""

    class UnregisteredRequest:
        pass

    assert get_response_type(UnregisteredRequest) is None


def test_get_all_request_types() -> None:
    """Test retrieving all registered request types."""

    class Response1:
        pass

    class Response2:
        pass

    class Request1(Request[Response1]):
        pass

    class Request2(Request[Response2]):
        pass

    all_types = get_all_request_types()

    assert Request1 in all_types
    assert Request2 in all_types


# ========== RequestHandler Registry Tests ==========


def test_register_and_get_handler() -> None:
    """Test registering and retrieving handlers."""

    class TestResponse:
        pass

    class TestRequest(Request[TestResponse]):
        pass

    class TestHandler(RequestHandler[TestRequest]):
        def __call__(self, request: TestRequest) -> TestResponse:
            return TestResponse()

    # RequestHandler should be auto-registered by RequestHandler metaclass
    assert has_handler(TestRequest)
    assert get_handler_class(TestRequest) == TestHandler


def test_has_handler() -> None:
    """Test checking if request type has a registered handler."""

    class HandledResponse:
        pass

    class UnhandledResponse:
        pass

    class HandledRequest(Request[HandledResponse]):
        pass

    class UnhandledRequest(Request[UnhandledResponse]):
        pass

    class MyHandler(RequestHandler[HandledRequest]):
        def __call__(self, request: HandledRequest) -> HandledResponse:
            return HandledResponse()

    assert has_handler(HandledRequest)
    assert not has_handler(UnhandledRequest)


def test_get_handler_class_returns_none_for_unregistered() -> None:
    """Test that getting unregistered handler returns None."""

    class UnhandledResponse:
        pass

    class UnhandledRequest(Request[UnhandledResponse]):
        pass

    assert get_handler_class(UnhandledRequest) is None


def test_get_all_handler_request_types() -> None:
    """Test retrieving all request types with registered handlers."""

    class Response1:
        pass

    class Response2:
        pass

    class Request1(Request[Response1]):
        pass

    class Request2(Request[Response2]):
        pass

    class Handler1(RequestHandler[Request1]):
        def __call__(self, request: Request1) -> Response1:
            return Response1()

    class Handler2(RequestHandler[Request2]):
        def __call__(self, request: Request2) -> Response2:
            return Response2()

    all_handler_types = get_all_handler_request_types()

    assert Request1 in all_handler_types
    assert Request2 in all_handler_types


# ========== Registry Management Tests ==========


def test_clear_all_registries() -> None:
    """Test clearing all registries."""

    class Response:
        pass

    class Request1(Request[Response]):
        pass

    class Handler1(RequestHandler[Request1]):
        def __call__(self, request: Request1) -> Response:
            return Response()

    # Verify they're registered
    assert has_response_type(Request1)
    assert has_handler(Request1)

    # Clear registries
    clear_all_registries()

    # Verify they're cleared
    assert not has_response_type(Request1)
    assert not has_handler(Request1)


def test_get_registry_stats() -> None:
    """Test getting registry statistics."""
    clear_all_registries()

    class Response1:
        pass

    class Response2:
        pass

    class Request1(Request[Response1]):
        pass

    class Request2(Request[Response2]):
        pass

    class Handler1(RequestHandler[Request1]):
        def __call__(self, request: Request1) -> Response1:
            return Response1()

    stats = get_registry_stats()

    assert stats["request_count"] >= 1  # At least Request1
    assert stats["handler_count"] >= 1  # At least Handler1
    assert isinstance(stats["request_count"], int)
    assert isinstance(stats["handler_count"], int)


# ========== Thread Safety Tests ==========


def test_concurrent_registrations() -> None:
    """Test that concurrent manual registrations are thread-safe."""
    clear_all_registries()

    num_threads = 10
    results: list[bool] = []

    def register_types(index: int) -> None:
        # Create unique types for this thread
        response_type = type(f"Response{index}", (), {})
        request_type = type(f"Request{index}", (), {})

        # Manually register
        register_request_response_type(request_type, response_type)

        # Verify registration succeeded
        results.append(has_response_type(request_type))

    threads = [threading.Thread(target=register_types, args=(i,)) for i in range(num_threads)]

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Verify all registrations succeeded
    assert len(results) == num_threads
    assert all(results)


def test_concurrent_reads() -> None:
    """Test that concurrent reads are thread-safe."""

    class Response:
        pass

    class TestRequest(Request[Response]):
        pass

    results: list[Any] = []
    num_threads = 10

    def read_response_type() -> None:
        results.append(get_response_type(TestRequest))

    threads = [threading.Thread(target=read_response_type) for _ in range(num_threads)]

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # All reads should return the same response type
    assert len(results) == num_threads
    assert all(r == Response for r in results)


# ========== Edge Cases ==========


def test_direct_registration_via_api() -> None:
    """Test that direct API registration works (for advanced use cases)."""

    class CustomResponse:
        pass

    class CustomRequest:
        pass

    # Manually register (bypassing Request[T] inheritance)
    register_request_response_type(CustomRequest, CustomResponse)

    assert has_response_type(CustomRequest)
    assert get_response_type(CustomRequest) == CustomResponse


def test_handler_already_registered_error() -> None:
    """Test that attempting to register a second handler raises HandlerAlreadyRegisteredError."""
    import pytest

    from pymediate import HandlerAlreadyRegisteredError

    class Response:
        pass

    class TestRequest(Request[Response]):
        pass

    class Handler1(RequestHandler[TestRequest]):
        def __call__(self, request: TestRequest) -> Response:
            return Response()

    assert get_handler_class(TestRequest) == Handler1

    # Attempting to register a second handler should raise error
    with pytest.raises(HandlerAlreadyRegisteredError) as exc_info:

        class Handler2(RequestHandler[TestRequest]):
            def __call__(self, request: TestRequest) -> Response:
                return Response()

    # Verify error details
    error = exc_info.value
    assert error.request_type == TestRequest
    assert error.existing_handler == Handler1
    assert "Handler1" in str(error)
    assert "Handler2" in str(error)


def test_handler_registration_error_preserves_first_handler() -> None:
    """Test that the first handler remains registered after registration error."""
    import pytest

    from pymediate import HandlerAlreadyRegisteredError

    class Response:
        pass

    class TestRequest(Request[Response]):
        pass

    class Handler1(RequestHandler[TestRequest]):
        def __call__(self, request: TestRequest) -> Response:
            return Response()

    # Verify first handler is registered
    assert get_handler_class(TestRequest) == Handler1

    # Attempt to register second handler
    with pytest.raises(HandlerAlreadyRegisteredError):

        class Handler2(RequestHandler[TestRequest]):
            def __call__(self, request: TestRequest) -> Response:
                return Response()

    # First handler should still be registered
    assert get_handler_class(TestRequest) == Handler1


def test_handler_registration_error_includes_location() -> None:
    """Test that registration error includes file location when available."""
    import pytest

    from pymediate import HandlerAlreadyRegisteredError

    class Response:
        pass

    class TestRequest(Request[Response]):
        pass

    class Handler1(RequestHandler[TestRequest]):
        def __call__(self, request: TestRequest) -> Response:
            return Response()

    # Attempt to register second handler
    with pytest.raises(HandlerAlreadyRegisteredError) as exc_info:

        class Handler2(RequestHandler[TestRequest]):
            def __call__(self, request: TestRequest) -> Response:
                return Response()

    # Error should have location info (may be <frozen abc> due to protocol machinery)
    error = exc_info.value
    assert error.existing_location is not None
    # Location should have format "filename:lineno"
    assert ":" in error.existing_location


def test_handler_registration_error_provides_solutions() -> None:
    """Test that registration error provides actionable solutions."""
    import pytest

    from pymediate import HandlerAlreadyRegisteredError

    class Response:
        pass

    class TestRequest(Request[Response]):
        pass

    class Handler1(RequestHandler[TestRequest]):
        def __call__(self, request: TestRequest) -> Response:
            return Response()

    # Attempt to register second handler
    with pytest.raises(HandlerAlreadyRegisteredError) as exc_info:

        class Handler2(RequestHandler[TestRequest]):
            def __call__(self, request: TestRequest) -> Response:
                return Response()

    # Error message should provide helpful solutions
    error_message = str(exc_info.value)
    assert "Solutions:" in error_message or "Solution:" in error_message
    assert "ONE handler" in error_message
    # Should suggest using different request types
    assert "V1" in error_message or "different request types" in error_message.lower()
