"""Shared base logic for both sync and async handlers.

This module provides HandlerBaseMixin which contains all the type extraction,
validation, and registration logic that is common between sync and async handlers.
"""

import inspect
from typing import Any, get_args, get_origin, get_type_hints

from .. import errors
from . import registry


def _qualified_name(annotation: object) -> str:
    """Render a type annotation as a module-qualified name for error messages.

    Falls back to ``str()`` for anything without ``__qualname__``/``__name__``
    (e.g. an unresolved string annotation). Builtins are shown unqualified.
    """
    qualname = getattr(annotation, "__qualname__", None) or getattr(annotation, "__name__", None)
    if qualname is None:
        return str(annotation)
    module = getattr(annotation, "__module__", None)
    if module is None or module == "builtins":
        return str(qualname)
    return f"{module}.{qualname}"


def _require_call_method(cls: type) -> Any:
    """Return the class's own ``__call__`, or raise if it doesn't define one.

    Args:
        cls: The handler class to inspect.

    Returns:
        The ``__call__`` function object from ``cls.__dict__``.

    Raises:
        InvalidHandlerSignatureError: If ``cls`` does not define ``__call__``.
    """
    if "__call__" not in cls.__dict__:
        raise errors.InvalidHandlerSignatureError(cls, "must implement __call__ method")
    return cls.__dict__["__call__"]


def _resolve_call_annotations(cls: type, call_method: Any) -> tuple[Any, Any]:
    """Validate __call__'s parameter shape and return its resolved annotations.

    Enforces the structural contract shared by request, event, and stream handlers:
    exactly one parameter besides ``self``, both it and the return annotated. String
    (PEP 563) annotations are resolved via ``get_type_hints``; if resolution fails,
    the raw annotations are returned so the caller's comparison reports the mismatch.

    Args:
        cls: The handler class (named in error messages).
        call_method: The ``__call__`` function object.

    Returns:
        A ``(request_annotation, return_annotation)`` tuple.

    Raises:
        InvalidHandlerSignatureError: If the parameter count or annotations are wrong.
    """
    sig = inspect.signature(call_method)

    params = list(sig.parameters.values())
    if len(params) != 2:  # self, request
        raise errors.InvalidHandlerSignatureError(
            cls,
            f"__call__ must accept exactly one parameter (besides self), got {len(params) - 1}",
        )

    request_param = params[1]  # Skip 'self'
    if request_param.annotation == inspect.Parameter.empty:
        raise errors.InvalidHandlerSignatureError(
            cls, "__call__ request parameter must have type annotation"
        )

    if sig.return_annotation == inspect.Signature.empty:
        raise errors.InvalidHandlerSignatureError(cls, "__call__ must have return type annotation")

    try:
        hints = get_type_hints(call_method)
    except Exception:
        hints = {}
    request_annotation = hints.get(request_param.name, request_param.annotation)
    return_annotation = hints.get("return", sig.return_annotation)
    return request_annotation, return_annotation


def _validate_request_annotation(
    cls: type,
    request_annotation: object,
    expected_request_type: type,
    *,
    kind: str = "request",
    declaration_name: str = "RequestHandler",
) -> None:
    """Enforce ADR 0004's exact-annotation contract for the request parameter.

    Dispatch is keyed by ``type(request)``, so the parameter must annotate the exact
    declared class - a base class or union passes static checking (contravariance) but
    is rejected here.

    Args:
        cls: The handler class (named in error messages).
        request_annotation: The resolved parameter annotation.
        expected_request_type: The exact class the parameter must annotate.
        kind: What the parameter is called in error messages ("request" or "event").
        declaration_name: The generic base class named in error messages.

    Raises:
        InvalidHandlerSignatureError: If the annotation isn't the exact expected type.
    """
    if request_annotation != expected_request_type:
        issue = (
            f"__call__ parameter must annotate the exact {kind} class declared in "
            f"{declaration_name}[...]: expected {_qualified_name(expected_request_type)}, "
            f"got {_qualified_name(request_annotation)}"
        )
        if isinstance(request_annotation, type) and issubclass(
            expected_request_type, request_annotation
        ):
            issue += (
                f" (a base class of {expected_request_type.__name__}). PyMediate dispatches "
                f"on the exact {kind} class, so a broader annotation is not accepted even "
                "though static type checkers allow it"
            )
        raise errors.InvalidHandlerSignatureError(cls, issue)


def _validate_call_signature(
    cls: type,
    expected_request_type: type,
    expected_response_type: type,
    is_async: bool = False,
    *,
    kind: str = "request",
    declaration_name: str = "RequestHandler",
) -> None:
    """Validate that the handler's __call__ method has the correct signature.

    Args:
        cls: The handler class to validate
        expected_request_type: The expected request parameter type
        expected_response_type: The expected return type
        is_async: Whether to expect async def __call__ or sync def __call__
        kind: What the parameter is called in error messages ("request" or "event")
        declaration_name: The generic base class named in error messages

    Raises:
        TypeError: If the signature doesn't match expectations
    """
    call_method = _require_call_method(cls)

    # Check if it's async when it should be (or vice versa)
    if is_async and not inspect.iscoroutinefunction(call_method):
        raise errors.InvalidHandlerSignatureError(
            cls, "__call__ must be async (use 'async def __call__')"
        )
    elif not is_async and inspect.iscoroutinefunction(call_method):
        raise errors.InvalidHandlerSignatureError(
            cls, "__call__ must be sync (remove 'async' from 'def __call__')"
        )

    request_annotation, return_annotation = _resolve_call_annotations(cls, call_method)
    _validate_request_annotation(
        cls, request_annotation, expected_request_type, kind=kind, declaration_name=declaration_name
    )

    if return_annotation != expected_response_type:
        raise errors.ResponseTypeMismatchError(cls, expected_response_type, return_annotation)


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

        This hook is automatically called when a new RequestHandler subclass is defined.
        It extracts the request type from RequestHandler[RequestType], looks up the
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

        # Extract request type from RequestHandler[RequestType]
        # We need to find the right base class (sync or async RequestHandler)
        orig_bases = getattr(cls, "__orig_bases__", ())
        for base in orig_bases:
            origin = get_origin(base)
            # Check if this is a RequestHandler-like class (has HandlerBaseMixin in its mro)
            if origin and any(hasattr(b, "_is_async") for b in getattr(origin, "__mro__", [])):
                args = get_args(base)
                if args:
                    cls._request_type = args[0]
                    break

        # Look up response type from request registry
        if cls._request_type is not None:
            if registry.has_response_type(cls._request_type):
                cls._response_type = registry.get_response_type(cls._request_type)

                # Validate the __call__ signature
                assert cls._response_type is not None, (
                    "Response type should not be None after check"
                )
                _validate_call_signature(
                    cls, cls._request_type, cls._response_type, is_async=cls._is_async
                )

                # Register handler
                registry.register_handler(cls._request_type, cls)
            else:
                # Only raise if this isn't a base RequestHandler class
                if cls.__name__ not in ("RequestHandler", "HandlerBaseMixin"):
                    raise errors.InvalidRequestTypeError(cls._request_type)

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
        if not registry.has_handler(request_type):
            available = registry.get_all_handler_request_types()
            raise errors.HandlerNotFoundError(request_type, available)
        return registry.get_handler_class(request_type)
