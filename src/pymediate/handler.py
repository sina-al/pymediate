"""Handler base class for the mediator pattern."""

import inspect
from typing import Any, get_args, get_origin

from pymediate.registry import _HANDLER_REGISTRY, _REQUEST_REGISTRY


def _validate_call_signature(
    cls: type, expected_request_type: type, expected_response_type: type
) -> None:
    """Validate that the handler's __call__ method has the correct signature.

    Args:
        cls: The handler class to validate
        expected_request_type: The expected request parameter type
        expected_response_type: The expected return type

    Raises:
        TypeError: If the signature doesn't match expectations
    """
    if "__call__" not in cls.__dict__:
        raise TypeError(f"{cls.__name__} must implement __call__ method")

    call_method = cls.__dict__["__call__"]
    sig = inspect.signature(call_method)

    # Validate parameters
    params = list(sig.parameters.values())
    if len(params) != 2:  # self, request
        raise TypeError(
            f"{cls.__name__}.__call__ must accept exactly one parameter "
            f"(besides self), got {len(params) - 1}"
        )

    request_param = params[1]  # Skip 'self'
    if request_param.annotation == inspect.Parameter.empty:
        raise TypeError(f"{cls.__name__}.__call__ request parameter must have type annotation")

    if request_param.annotation != expected_request_type:
        param_name = (
            request_param.annotation.__name__
            if hasattr(request_param.annotation, "__name__")
            else str(request_param.annotation)
        )
        raise TypeError(
            f"{cls.__name__}.__call__ parameter must be of type "
            f"{expected_request_type.__name__}, got {param_name}"
        )

    # Validate return type
    if sig.return_annotation == inspect.Signature.empty:
        raise TypeError(f"{cls.__name__}.__call__ must have return type annotation")

    if sig.return_annotation != expected_response_type:
        return_name = (
            sig.return_annotation.__name__
            if hasattr(sig.return_annotation, "__name__")
            else str(sig.return_annotation)
        )
        raise TypeError(
            f"{cls.__name__}.__call__ must return {expected_response_type.__name__}, "
            f"got {return_name}"
        )


class Handler[RequestT]:
    """Base handler class with automatic response type inference.

    The handler only needs to specify the request type. The response type
    is automatically inferred from the Request class definition.

    Example:
        class UserResponse:
            def __init__(self, user_id: int):
                self.user_id = user_id

        class CreateUserRequest(Request[UserResponse]):
            def __init__(self, name: str):
                self.name = name

        class CreateUserHandler(Handler[CreateUserRequest]):
            def __call__(self, request: CreateUserRequest) -> UserResponse:
                return UserResponse(user_id=1)

    The handler validates at class definition time that:
    - __call__ accepts the correct request type
    - __call__ returns the correct response type
    """

    _request_type: type | None = None
    _response_type: type | None = None

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Extract request type and validate handler signature."""
        super().__init_subclass__(**kwargs)

        cls._request_type = None
        cls._response_type = None

        # Extract request type from Handler[RequestType]
        orig_bases = getattr(cls, "__orig_bases__", ())
        for base in orig_bases:
            origin = get_origin(base)
            if origin is Handler:
                args = get_args(base)
                if args:
                    cls._request_type = args[0]
                    break

        # Look up response type from request registry
        if cls._request_type is not None:
            if cls._request_type in _REQUEST_REGISTRY:
                cls._response_type = _REQUEST_REGISTRY[cls._request_type]

                # Validate the __call__ signature
                _validate_call_signature(cls, cls._request_type, cls._response_type)

                # Register handler
                _HANDLER_REGISTRY[cls._request_type] = cls
            else:
                # Only raise if this isn't the base Handler class
                if cls.__name__ != "Handler":
                    raise TypeError(
                        f"{cls.__name__}: Request type {cls._request_type.__name__} "
                        f"must be a subclass of Request with response type specified"
                    )

    def __call__(self, request: RequestT) -> Any:  # noqa: ARG002
        """Handle the request and return a response.

        This method must be implemented by subclasses with the correct signature.

        Args:
            request: The request to handle

        Returns:
            The response (type determined by the request's response type)
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement __call__ method")

    @classmethod
    def get_request_type(cls) -> type | None:
        """Get the request type this handler handles."""
        return cls._request_type

    @classmethod
    def get_response_type(cls) -> type | None:
        """Get the response type this handler returns."""
        return cls._response_type

    @classmethod
    def get_handler_for_request(cls, request_type: type) -> Any:
        """Get the handler class registered for a given request type.

        Args:
            request_type: The request type to look up

        Returns:
            The handler class for that request type

        Raises:
            ValueError: If no handler is registered for the request type
        """
        if request_type not in _HANDLER_REGISTRY:
            raise ValueError(f"No handler registered for request type {request_type.__name__}")
        return _HANDLER_REGISTRY[request_type]
