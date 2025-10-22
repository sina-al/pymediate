"""Synchronous handler base class for the mediator pattern."""

from abc import ABC, abstractmethod
from typing import Any

from ._internal.handler import HandlerBaseMixin


class Handler[RequestT](HandlerBaseMixin[RequestT], ABC):
    """Abstract base handler class for synchronous request processing.

    Handlers contain the business logic for processing requests. They only need
    to specify the request type - the response type is automatically inferred
    from the Request[ResponseT] class definition.

    The handler performs compile-time validation via __init_subclass__ to ensure:
    - The __call__ method exists and is properly implemented
    - The __call__ method is synchronous (not async)
    - The __call__ parameter matches the declared request type
    - The __call__ return type matches the request's response type

    This validation happens at class definition time (import time), catching
    errors early in the development cycle rather than at runtime.

    As an abstract base class, Handler cannot be instantiated directly and
    subclasses must implement the __call__ method. This ensures mypy will
    catch missing or incorrect __call__ implementations.

    Type Parameters:
        RequestT: The type of request this handler processes.

    Examples:
        Basic handler with dataclasses:
            ```python
            from dataclasses import dataclass
            from pymediate import Handler, Request

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
        For asynchronous handlers, use `pymediate.aio.Handler` instead.
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
        - pymediate.aio.Handler: Async handler variant
        - pymediate.aio.Mediator: Async mediator variant
    """

    _is_async = False  # Mark this as a synchronous handler

    @abstractmethod
    def __call__(self, request: RequestT) -> Any:
        """Handle the request and return a response.

        This is an abstract method that must be implemented by all Handler subclasses.
        Mypy will enforce that subclasses properly override this method with the
        correct type signature.

        Args:
            request: The request to handle

        Returns:
            The response (type determined by the request's response type)

        Note:
            Subclasses must implement this with the signature:
            `def __call__(self, request: RequestType) -> ResponseType: ...`

            This must be a synchronous method. For async handlers, use
            `pymediate.aio.Handler` instead.
        """
        ...
