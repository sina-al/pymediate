"""Synchronous handler base class for the mediator pattern."""

from abc import ABC, abstractmethod
from typing import Any

from .._internal.handler import HandlerBaseMixin


class RequestHandler[RequestT](HandlerBaseMixin[RequestT], ABC):
    """Abstract base handler class for synchronous request processing.

    Handlers contain the business logic for processing requests. They only need
    to specify the request type - the response type is automatically inferred
    from the Request[ResponseT] class definition.

    The handler performs class-definition-time validation via __init_subclass__ to ensure:
    - The __call__ method exists and is properly implemented
    - The __call__ method is synchronous (not async)
    - The __call__ parameter annotates the exact declared request type
      (not a base class or union)
    - The __call__ return type matches the request's response type

    This validation happens at class definition time (import time), catching
    errors early in the development cycle rather than at runtime.

    As an abstract base class, RequestHandler cannot be instantiated directly - subclasses
    must implement `__call__`, and mypy flags subclasses that omit it or type its
    request parameter incorrectly.

    Type Parameters:
        RequestT: The type of request this handler processes.

    Examples:
        Basic handler with dataclasses:
            ```python
            from dataclasses import dataclass
            from pymediate.sync import Request, RequestHandler

            @dataclass
            class UserResponse:
                user_id: int
                username: str

            @dataclass
            class CreateUserRequest(Request[UserResponse]):
                username: str
                email: str

            class CreateUserHandler(RequestHandler[CreateUserRequest]):
                def __call__(self, request: CreateUserRequest) -> UserResponse:
                    return UserResponse(user_id=1, username=request.username)
            ```

        RequestHandler with dependencies:
            ```python
            class CreateUserHandler(RequestHandler[CreateUserRequest]):
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
        For asynchronous handlers, use `pymediate.RequestHandler` instead.
        Validation occurs at class definition time. If your __call__ signature
        doesn't match expectations, you'll get a clear error message when the
        module is imported, not when the handler is invoked.

    Raises:
        InvalidHandlerSignatureError: If __call__ signature is invalid.
        InvalidRequestTypeError: If request type doesn't inherit from Request.
        ResponseTypeMismatchError: If return type doesn't match expected response.

    See Also:
        - Request: Base request class
        - Mediator: Routes requests to handlers (sync version)
        - pymediate.RequestHandler: Async handler variant
        - pymediate.Mediator: Async mediator variant
    """

    _is_async = False  # Mark this as a synchronous handler

    @abstractmethod
    def __call__(self, request: RequestT) -> Any:
        """Handle the request and return a response.

        This is an abstract method that must be implemented by all RequestHandler subclasses,
        with the signature `def __call__(self, request: RequestType) -> ResponseType: ...`

        Args:
            request: The request to handle.

        Returns:
            The response, of the type declared by the request's `Request[ResponseType]`.

        Note:
            mypy checks that `request`'s type matches `RequestHandler[RequestT]`'s type
            argument, but not that the return type matches the request's declared
            response type - that mismatch is caught at runtime instead, when the
            class is defined (see `ResponseTypeMismatchError`). The annotation must
            be the exact request class - a base class or union passes static
            checking (contravariance) but raises `InvalidHandlerSignatureError` at
            class definition. This method must also be synchronous; for async
            handlers, use `pymediate.RequestHandler`.
        """
        ...
