"""Global registries for request/response type mappings and handler registrations.

This module provides thread-safe registration and lookup of request-response type
mappings and request-handler class mappings. These registries are populated
automatically via __init_subclass__ hooks in Request and RequestHandler classes.

Warning:
    This module is internal to PyMediate. Package consumers should not access
    these registries directly. Package developers should use the provided API
    functions for registry operations that need locking.

Thread Safety:
    Writes and multi-key reads (snapshots, clears) are protected by locks.
    Single-key lookups read the dicts directly - a one-key dict read is atomic
    in CPython, and these sit on the per-send hot path where a lock acquisition
    per dispatch is measurable overhead.
"""

import inspect
import threading
from dataclasses import dataclass

# Module-level locks for thread safety
_request_lock = threading.RLock()
_handler_lock = threading.RLock()
_event_lock = threading.RLock()


@dataclass(frozen=True)
class HandlerRegistration:
    """Tracks a handler class and where it was registered.

    This groups handler metadata together for cleaner data management.

    Attributes:
        handler_class: The handler class registered for a request type.
        location: File path and line number where handler was registered (for error messages).
    """

    handler_class: type
    location: str | None


# Internal registries - not for direct access
# Maps request types to their response types
# Example: {CreateUserRequest: UserCreatedResponse}
_REQUEST_REGISTRY: dict[type, type] = {}

# Maps request types to their handler registration info
# Example: {CreateUserRequest: HandlerRegistration(CreateUserHandler, "/path/file.py:42")}
_HANDLER_REGISTRY: dict[type, HandlerRegistration] = {}

# Maps event types to every handler class registered for them, in registration order.
# Values are immutable tuples replaced wholesale on registration, so single-key reads
# are safe without a lock (same design as the other hot-path lookups above).
# Example: {OrderPlaced: (SendConfirmation, UpdateAnalytics)}
_EVENT_HANDLER_REGISTRY: dict[type, tuple[type, ...]] = {}


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

    Thread-safe without a lock: a single-key dict read is atomic in CPython,
    and this sits on the per-send hot path.

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
    return _REQUEST_REGISTRY.get(request_type)


def has_response_type(request_type: type) -> bool:
    """Check if a request type has a registered response type.

    Thread-safe without a lock: a single-key dict read is atomic in CPython.

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
# Request-handler registry API
# ============================================================================


def _get_user_code_location() -> str | None:
    """Find the user's code location, skipping pymediate internal frames.

    Walks up the call stack to find the first frame that's not inside the
    pymediate package, which represents the user's handler definition.

    Returns:
        A string in the format "filename:lineno" or None if not found.

    Note:
        This is used for providing helpful error messages showing where
        handlers were registered.
    """
    frame = inspect.currentframe()
    if frame is None:
        return None

    try:
        # Skip 2 frames: this function + register_handler
        for _ in range(2):
            if frame.f_back is None:
                return None
            frame = frame.f_back

        # Walk up to find first non-pymediate frame
        max_depth = 10
        for _ in range(max_depth):
            if frame is None:
                return None

            filename = frame.f_code.co_filename
            # Skip pymediate package files (handle both Unix and Windows paths)
            if "/pymediate/" not in filename and "\\pymediate\\" not in filename:
                return f"{filename}:{frame.f_lineno}"

            frame = frame.f_back

        return None
    finally:
        del frame  # Avoid reference cycles


def register_handler(request_type: type, handler_class: type) -> None:
    """Register a handler class for a request type.

    This function is called automatically when a RequestHandler[RequestT] subclass is
    defined via __init_subclass__. It stores the mapping so handlers can be
    looked up by request type.

    PyMediate enforces a one-handler-per-request policy. If a handler is already
    registered for the given request type, this will raise HandlerAlreadyRegisteredError
    with helpful information about where the first handler was registered.

    Thread-safe: Uses a lock to prevent race conditions in multi-threaded environments.

    Args:
        request_type: The request class this handler processes.
        handler_class: The handler class that processes this request type.

    Raises:
        HandlerAlreadyRegisteredError: If a handler is already registered for this request type.

    Examples:
        ```python
        # This is called automatically by RequestHandler.__init_subclass__
        # You typically don't call this directly
        register_handler(CreateUserRequest, CreateUserHandler)
        ```

    Note:
        This is an internal API for PyMediate developers. Package consumers
        should not call this function directly - it's handled automatically
        by the RequestHandler base class.
    """
    with _handler_lock:
        # Check if handler already exists
        if request_type in _HANDLER_REGISTRY:
            existing = _HANDLER_REGISTRY[request_type]

            # Import here to avoid circular dependency
            from ..errors import HandlerAlreadyRegisteredError

            raise HandlerAlreadyRegisteredError(
                request_type=request_type,
                existing_handler=existing.handler_class,
                new_handler=handler_class,
                existing_location=existing.location,
            )

        # Track registration location for better error messages
        location = _get_user_code_location()

        # Register the handler with its metadata
        _HANDLER_REGISTRY[request_type] = HandlerRegistration(
            handler_class=handler_class,
            location=location,
        )


def get_handler_class(request_type: type) -> type | None:
    """Get the handler class for a given request type.

    Thread-safe without a lock: a single-key dict read is atomic in CPython,
    and this sits on the per-send hot path.

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
    registration = _HANDLER_REGISTRY.get(request_type)
    return registration.handler_class if registration else None


def has_handler(request_type: type) -> bool:
    """Check if a handler is registered for a request type.

    Thread-safe without a lock: a single-key dict read is atomic in CPython.

    Args:
        request_type: The request class to check.

    Returns:
        True if a handler is registered for this request type, False otherwise.

    Examples:
        ```python
        if has_handler(CreateUserRequest):
            print("RequestHandler registered for CreateUserRequest")
        ```

    Note:
        This is an internal API for PyMediate developers.
    """
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
# Event-RequestHandler Registry API
# ============================================================================


def register_event_handler(event_type: type, handler_class: type) -> None:
    """Register an event handler class for an event type.

    This function is called automatically when an EventHandler[EventT] subclass
    is defined via __init_subclass__. Unlike request handlers, any number of
    handlers may register for the same event type; they are stored in
    registration order, which is the order publish() invokes them in.

    Thread-safe: Uses a lock to prevent race conditions in multi-threaded environments.

    Args:
        event_type: The event class this handler subscribes to.
        handler_class: The handler class to append to the event's handler list.

    Examples:
        ```python
        # This is called automatically by EventHandler.__init_subclass__
        # You typically don't call this directly
        register_event_handler(OrderPlaced, SendConfirmation)
        ```

    Note:
        This is an internal API for PyMediate developers. Package consumers
        should not call this function directly - it's handled automatically
        by the EventHandler base class.
    """
    with _event_lock:
        existing = _EVENT_HANDLER_REGISTRY.get(event_type, ())
        _EVENT_HANDLER_REGISTRY[event_type] = (*existing, handler_class)


def get_event_handler_classes(event_type: type) -> tuple[type, ...]:
    """Get every handler class registered for an event type, in registration order.

    Thread-safe without a lock: values are immutable tuples replaced wholesale on
    registration, and a single-key dict read is atomic in CPython - this sits on
    the per-publish hot path.

    Args:
        event_type: The event class to look up.

    Returns:
        The handler classes registered for this event type, empty if none.

    Note:
        This is an internal API for PyMediate developers.
    """
    return _EVENT_HANDLER_REGISTRY.get(event_type, ())


def has_event_handlers(event_type: type) -> bool:
    """Check if any handler is registered for an event type.

    Thread-safe without a lock: a single-key dict read is atomic in CPython.

    Args:
        event_type: The event class to check.

    Returns:
        True if at least one handler is registered for this event type.

    Note:
        This is an internal API for PyMediate developers.
    """
    return event_type in _EVENT_HANDLER_REGISTRY


def get_all_event_types() -> list[type]:
    """Get all event types that have registered handlers.

    Thread-safe: Returns a snapshot of the current registry state.

    Returns:
        A list of all event types with at least one registered handler.

    Note:
        This is an internal API for PyMediate developers, primarily used
        for debugging and testing.
    """
    with _event_lock:
        return list(_EVENT_HANDLER_REGISTRY.keys())


# ============================================================================
# Testing/Debugging Utilities
# ============================================================================


def clear_handler_registry() -> None:
    """Clear handler registrations, request and event alike (for testing purposes only).

    This function clears request-handler and event-handler registrations while
    preserving request-response type mappings. This is useful for test isolation
    where you want to clear dynamic handler registrations but keep static type
    relationships.

    Thread-safe: Uses locks to ensure consistent state during clearing.

    Examples:
        ```python
        # In a pytest fixture for test isolation
        @pytest.fixture(autouse=True)
        def cleanup():
            yield
            clear_handler_registry()
        ```

    Note:
        This is an internal API for PyMediate testing. Prefer this over
        clear_all_registries() for test isolation since request-response
        type mappings are static relationships that don't need clearing.
    """
    with _handler_lock:
        _HANDLER_REGISTRY.clear()
    with _event_lock:
        _EVENT_HANDLER_REGISTRY.clear()


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
        This is an internal API for PyMediate testing. For test isolation,
        prefer clear_handler_registry() which only clears handlers.
    """
    with _request_lock:
        with _handler_lock:
            with _event_lock:
                _REQUEST_REGISTRY.clear()
                _HANDLER_REGISTRY.clear()
                _EVENT_HANDLER_REGISTRY.clear()


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
            with _event_lock:
                return {
                    "request_count": len(_REQUEST_REGISTRY),
                    "handler_count": len(_HANDLER_REGISTRY),
                    "event_handler_count": len(_EVENT_HANDLER_REGISTRY),
                }
