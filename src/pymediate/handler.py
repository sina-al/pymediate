"""Handler base class for the mediator pattern."""

import inspect
from typing import Any, get_args, get_origin

from pymediate.errors import (
    HandlerNotFoundError,
    InvalidHandlerSignatureError,
    InvalidRequestTypeError,
    ResponseTypeMismatchError,
)
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
        raise InvalidHandlerSignatureError(cls, "must implement __call__ method")

    call_method = cls.__dict__["__call__"]
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


class Handler[RequestT]:
    """Base handler class with automatic response type inference.

    Handlers contain the business logic for processing requests. They only need
    to specify the request type - the response type is automatically inferred
    from the Request[ResponseT] class definition.

    The handler performs compile-time validation via __init_subclass__ to ensure:
    - The __call__ method exists and is properly implemented
    - The __call__ parameter matches the declared request type
    - The __call__ return type matches the request's response type

    This validation happens at class definition time (import time), catching
    errors early in the development cycle rather than at runtime.

    Type Parameters:
        RequestT: The type of request this handler processes.

    Attributes:
        _request_type: Class-level attribute storing the request type.
        _response_type: Class-level attribute storing the inferred response type.

    Examples:
        Basic handler with dataclasses:
            ```python
            from dataclasses import dataclass

            @dataclass
            class UserResponse:
                user_id: int
                username: str

            @dataclass
            class CreateUserRequest(Request[UserResponse]):
                username: str
                email: str

            class CreateUserHandler(Handler[CreateUserRequest]):
                def __call__(self, request: CreateUserRequest) -> UserResponse:
                    return UserResponse(user_id=1, username=request.username)
            ```

        Handler with dependencies:
            ```python
            class CreateUserHandler(Handler[CreateUserRequest]):
                def __init__(self, database: Database):
                    self.database = database

                def __call__(self, request: CreateUserRequest) -> UserResponse:
                    user_id = self.database.insert_user(
                        username=request.username,
                        email=request.email
                    )
                    return UserResponse(user_id=user_id, username=request.username)
            ```

    Note:
        Validation occurs at class definition time. If your __call__ signature
        doesn't match expectations, you'll get a clear error message when the
        module is imported, not when the handler is invoked.

    Raises:
        InvalidHandlerSignatureError: If __call__ signature is invalid.
        InvalidRequestTypeError: If request type doesn't inherit from Request.
        ResponseTypeMismatchError: If return type doesn't match expected response.

    See Also:
        - Request: Base request class
        - Mediator: Routes requests to handlers
        - Resolver: Resolves handler instances
    """

    _request_type: type | None = None
    _response_type: type | None = None

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

        Note:
            This method is called automatically by Python when a subclass is created.
            You should not call this method directly.
        """
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
                    raise InvalidRequestTypeError(cls._request_type)

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
        """Get the request type this handler handles.

        Returns:
            The request type class that this handler is designed to process,
            or None if no request type was specified.

        Examples:
            ```python
            class MyHandler(Handler[MyRequest]):
                ...

            assert MyHandler.get_request_type() == MyRequest
            ```
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

        Examples:
            ```python
            class MyRequest(Request[MyResponse]):
                ...

            class MyHandler(Handler[MyRequest]):
                ...

            assert MyHandler.get_response_type() == MyResponse
            ```
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

        Examples:
            ```python
            handler_class = Handler.get_handler_for_request(CreateUserRequest)
            assert handler_class == CreateUserHandler
            ```

        Note:
            This returns the handler *class*, not an instance. Use a Resolver
            to get handler instances.
        """
        if request_type not in _HANDLER_REGISTRY:
            available = list(_HANDLER_REGISTRY.keys())
            raise HandlerNotFoundError(request_type, available)
        return _HANDLER_REGISTRY[request_type]
