"""Shared base logic for both sync and async handlers.

This module provides HandlerBaseMixin which contains all the type extraction,
validation, and registration logic that is common between sync and async handlers.
"""

import inspect
from typing import Any, get_args, get_origin

from pymediate.errors import (
    HandlerNotFoundError,
    InvalidHandlerSignatureError,
    InvalidRequestTypeError,
    ResponseTypeMismatchError,
)
from pymediate.registry import (
    get_all_handler_request_types,
    get_handler_class,
    get_response_type,
    has_handler,
    has_response_type,
    register_handler,
)


def _validate_call_signature(
    cls: type,
    expected_request_type: type,
    expected_response_type: type,
    is_async: bool = False,
) -> None:
    """Validate that the handler's __call__ method has the correct signature.

    Args:
        cls: The handler class to validate
        expected_request_type: The expected request parameter type
        expected_response_type: The expected return type
        is_async: Whether to expect async def __call__ or sync def __call__

    Raises:
        TypeError: If the signature doesn't match expectations
    """
    if "__call__" not in cls.__dict__:
        raise InvalidHandlerSignatureError(cls, "must implement __call__ method")

    call_method = cls.__dict__["__call__"]

    # Check if it's async when it should be (or vice versa)
    if is_async and not inspect.iscoroutinefunction(call_method):
        raise InvalidHandlerSignatureError(cls, "__call__ must be async (use 'async def __call__')")
    elif not is_async and inspect.iscoroutinefunction(call_method):
        raise InvalidHandlerSignatureError(
            cls, "__call__ must be sync (remove 'async' from 'def __call__')"
        )

    sig = inspect.signature(call_method)

    # Validate parameters
    params = list(sig.parameters.values())
    if len(params) != 2:  # self, request
        raise InvalidHandlerSignatureError(
            cls,
            f"__call__ must accept exactly one parameter (besides self), got {len(params) - 1}",
        )

    request_param = params[1]  # Skip 'self'
    if request_param.annotation == inspect.Parameter.empty:
        raise InvalidHandlerSignatureError(
            cls, "__call__ request parameter must have type annotation"
        )

    if request_param.annotation != expected_request_type:
        param_name = (
            request_param.annotation.__name__
            if hasattr(request_param.annotation, "__name__")
            else str(request_param.annotation)
        )
        expected_name = expected_request_type.__name__
        raise InvalidHandlerSignatureError(
            cls,
            f"__call__ parameter must be of type {expected_name}, got {param_name}",
        )

    # Validate return type
    if sig.return_annotation == inspect.Signature.empty:
        raise InvalidHandlerSignatureError(cls, "__call__ must have return type annotation")

    if sig.return_annotation != expected_response_type:
        raise ResponseTypeMismatchError(cls, expected_response_type, sig.return_annotation)


class HandlerBaseMixin[RequestT]:
    """Mixin providing shared logic for both sync and async handlers.

    This mixin contains all the type extraction, validation, and registration
    logic that is common between synchronous and asynchronous handlers.

    Type Parameters:
        RequestT: The type of request this handler processes.

    Attributes:
        _request_type: Class-level attribute storing the request type.
        _response_type: Class-level attribute storing the inferred response type.
    """

    _request_type: type | None = None
    _response_type: type | None = None
    _is_async: bool = False  # Set by subclass

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Extract request type and validate handler signature.

        This hook is automatically called when a new Handler subclass is defined.
        It extracts the request type from Handler[RequestType], looks up the
        corresponding response type, validates the __call__ signature, and
        registers the handler.

        Args:
            **kwargs: Additional keyword arguments passed to parent __init_subclass__.

        Raises:
            InvalidRequestTypeError: If the request type doesn't inherit from Request.
            InvalidHandlerSignatureError: If __call__ signature is invalid.
            ResponseTypeMismatchError: If return type doesn't match expected response.
        """
        super().__init_subclass__(**kwargs)

        cls._request_type = None
        cls._response_type = None

        # Extract request type from Handler[RequestType]
        # We need to find the right base class (could be Handler or AsyncHandler)
        orig_bases = getattr(cls, "__orig_bases__", ())
        for base in orig_bases:
            origin = get_origin(base)
            # Check if this is a Handler-like class (has HandlerBaseMixin in its mro)
            if origin and any(hasattr(b, "_is_async") for b in getattr(origin, "__mro__", [])):
                args = get_args(base)
                if args:
                    cls._request_type = args[0]
                    break

        # Look up response type from request registry
        if cls._request_type is not None:
            if has_response_type(cls._request_type):
                cls._response_type = get_response_type(cls._request_type)

                # Validate the __call__ signature
                assert cls._response_type is not None, (
                    "Response type should not be None after check"
                )
                _validate_call_signature(
                    cls, cls._request_type, cls._response_type, is_async=cls._is_async
                )

                # Register handler
                register_handler(cls._request_type, cls)
            else:
                # Only raise if this isn't a base Handler class
                if cls.__name__ not in ("Handler", "HandlerBaseMixin"):
                    raise InvalidRequestTypeError(cls._request_type)

    @classmethod
    def get_request_type(cls) -> type | None:
        """Get the request type this handler handles.

        Returns:
            The request type class that this handler is designed to process,
            or None if no request type was specified.
        """
        return cls._request_type

    @classmethod
    def get_response_type(cls) -> type | None:
        """Get the response type this handler returns.

        The response type is automatically inferred from the request's
        Request[ResponseT] declaration.

        Returns:
            The response type class that this handler will return,
            or None if no response type was registered.
        """
        return cls._response_type

    @classmethod
    def get_handler_for_request(cls, request_type: type) -> Any:
        """Get the handler class registered for a given request type.

        This is a class-level utility method for looking up which handler
        class is registered to handle a specific request type.

        Args:
            request_type: The request type class to look up.

        Returns:
            The handler class that processes the given request type.

        Raises:
            HandlerNotFoundError: If no handler is registered for the request type.
        """
        if not has_handler(request_type):
            available = get_all_handler_request_types()
            raise HandlerNotFoundError(request_type, available)
        return get_handler_class(request_type)
