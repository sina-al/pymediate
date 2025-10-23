"""Global registries for request/response type mappings and handler registrations.

This module provides thread-safe registration and lookup of request-response type
mappings and request-handler class mappings. These registries are populated
automatically via __init_subclass__ hooks in Request and Handler classes.

Warning:
    This module is internal to PyMediate. Package consumers should not access
    these registries directly. Package developers should use the provided API
    functions for type-safe, thread-safe registry operations.

Thread Safety:
    All registry operations are protected by locks to ensure thread safety in
    multi-threaded environments. This prevents race conditions when multiple
    threads are registering or looking up types concurrently.
"""

import threading
from typing import Any

# Module-level locks for thread safety
_request_lock = threading.RLock()
_handler_lock = threading.RLock()

# Internal registries - not for direct access
# Maps request types to their response types
# Example: {CreateUserRequest: UserCreatedResponse}
_REQUEST_REGISTRY: dict[type, type] = {}

# Maps request types to their handler classes
# Example: {CreateUserRequest: CreateUserHandler}
_HANDLER_REGISTRY: dict[type, Any] = {}


# ============================================================================
# Request-Response Type Registry API
# ============================================================================


def register_request_response_type(request_type: type, response_type: type) -> None:
    """Register a request type with its corresponding response type.

    This function is called automatically when a Request[ResponseT] subclass is
    defined via __init_subclass__. It stores the mapping so handlers can look up
    what response type they should return for a given request.

    Thread-safe: Uses a lock to prevent race conditions in multi-threaded environments.

    Args:
        request_type: The request class to register.
        response_type: The response type class that handlers should return for this request.

    Examples:
        ```python
        # This is called automatically by Request.__init_subclass__
        # You typically don't call this directly
        register_request_response_type(CreateUserRequest, UserCreatedResponse)
        ```

    Note:
        This is an internal API for PyMediate developers. Package consumers
        should not call this function directly - it's handled automatically
        by the Request base class.
    """
    with _request_lock:
        _REQUEST_REGISTRY[request_type] = response_type


def get_response_type(request_type: type) -> type | None:
    """Get the response type for a given request type.

    Thread-safe: Uses a lock to ensure consistent reads.

    Args:
        request_type: The request class to look up.

    Returns:
        The response type class for this request, or None if not registered.

    Examples:
        ```python
        response_type = get_response_type(CreateUserRequest)
        # Returns: UserCreatedResponse (or None if not registered)
        ```

    Note:
        This is an internal API for PyMediate developers. Package consumers
        should rely on type inference rather than calling this directly.
    """
    with _request_lock:
        return _REQUEST_REGISTRY.get(request_type)


def has_response_type(request_type: type) -> bool:
    """Check if a request type has a registered response type.

    Thread-safe: Uses a lock to ensure consistent reads.

    Args:
        request_type: The request class to check.

    Returns:
        True if the request type has a registered response type, False otherwise.

    Examples:
        ```python
        if has_response_type(CreateUserRequest):
            print("CreateUserRequest has a registered response type")
        ```

    Note:
        This is an internal API for PyMediate developers.
    """
    with _request_lock:
        return request_type in _REQUEST_REGISTRY


def get_all_request_types() -> list[type]:
    """Get all registered request types.

    Thread-safe: Returns a snapshot of the current registry state.

    Returns:
        A list of all request types that have been registered.

    Examples:
        ```python
        request_types = get_all_request_types()
        print(f"Registered requests: {[t.__name__ for t in request_types]}")
        ```

    Note:
        This is an internal API for PyMediate developers, primarily used
        for debugging and testing.
    """
    with _request_lock:
        return list(_REQUEST_REGISTRY.keys())


# ============================================================================
# Request-Handler Registry API
# ============================================================================


def register_handler(request_type: type, handler_class: type) -> None:
    """Register a handler class for a request type.

    This function is called automatically when a Handler[RequestT] subclass is
    defined via __init_subclass__. It stores the mapping so handlers can be
    looked up by request type.

    Thread-safe: Uses a lock to prevent race conditions in multi-threaded environments.

    Args:
        request_type: The request class this handler processes.
        handler_class: The handler class that processes this request type.

    Examples:
        ```python
        # This is called automatically by Handler.__init_subclass__
        # You typically don't call this directly
        register_handler(CreateUserRequest, CreateUserHandler)
        ```

    Note:
        This is an internal API for PyMediate developers. Package consumers
        should not call this function directly - it's handled automatically
        by the Handler base class.
    """
    with _handler_lock:
        _HANDLER_REGISTRY[request_type] = handler_class


def get_handler_class(request_type: type) -> type | None:
    """Get the handler class for a given request type.

    Thread-safe: Uses a lock to ensure consistent reads.

    Args:
        request_type: The request class to look up.

    Returns:
        The handler class for this request type, or None if not registered.

    Examples:
        ```python
        handler_class = get_handler_class(CreateUserRequest)
        # Returns: CreateUserHandler (or None if not registered)
        ```

    Note:
        This is an internal API for PyMediate developers. For resolving
        handler instances, use a ServiceProvider instead of calling this directly.
    """
    with _handler_lock:
        return _HANDLER_REGISTRY.get(request_type)


def has_handler(request_type: type) -> bool:
    """Check if a handler is registered for a request type.

    Thread-safe: Uses a lock to ensure consistent reads.

    Args:
        request_type: The request class to check.

    Returns:
        True if a handler is registered for this request type, False otherwise.

    Examples:
        ```python
        if has_handler(CreateUserRequest):
            print("Handler registered for CreateUserRequest")
        ```

    Note:
        This is an internal API for PyMediate developers.
    """
    with _handler_lock:
        return request_type in _HANDLER_REGISTRY


def get_all_handler_request_types() -> list[type]:
    """Get all request types that have registered handlers.

    Thread-safe: Returns a snapshot of the current registry state.

    Returns:
        A list of all request types that have registered handlers.

    Examples:
        ```python
        request_types = get_all_handler_request_types()
        print(f"Handlers registered for: {[t.__name__ for t in request_types]}")
        ```

    Note:
        This is an internal API for PyMediate developers, primarily used
        for debugging, testing, and error messages.
    """
    with _handler_lock:
        return list(_HANDLER_REGISTRY.keys())


# ============================================================================
# Testing/Debugging Utilities
# ============================================================================


def clear_all_registries() -> None:
    """Clear all registries (for testing purposes only).

    This function is intended for use in tests to ensure a clean state between
    test runs. It should not be used in production code.

    Thread-safe: Uses both locks to ensure consistent state during clearing.

    Warning:
        This will remove all registered request-response mappings and handlers.
        Only use this in test cleanup code.

    Examples:
        ```python
        # In a pytest fixture
        @pytest.fixture(autouse=True)
        def cleanup():
            yield
            clear_all_registries()
        ```

    Note:
        This is an internal API for PyMediate testing.
    """
    with _request_lock:
        with _handler_lock:
            _REQUEST_REGISTRY.clear()
            _HANDLER_REGISTRY.clear()


def get_registry_stats() -> dict[str, int]:
    """Get statistics about the current registry state.

    Thread-safe: Uses locks to ensure consistent reads.

    Returns:
        A dictionary with registry statistics including counts of registered
        requests and handlers.

    Examples:
        ```python
        stats = get_registry_stats()
        print(f"Registered requests: {stats['request_count']}")
        print(f"Registered handlers: {stats['handler_count']}")
        ```

    Note:
        This is an internal API for PyMediate developers, primarily used
        for debugging and monitoring.
    """
    with _request_lock:
        with _handler_lock:
            return {
                "request_count": len(_REQUEST_REGISTRY),
                "handler_count": len(_HANDLER_REGISTRY),
            }
