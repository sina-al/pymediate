"""Asynchronous handler base class for the mediator pattern."""

from abc import ABC, abstractmethod
from typing import Any

from ._internal.handler import HandlerBaseMixin


class RequestHandler[RequestT](HandlerBaseMixin[RequestT], ABC):
    """Abstract base handler class for asynchronous request processing.

    Async handlers contain the business logic for processing requests asynchronously.
    They only need to specify the request type - the response type is automatically
    inferred from the Request[ResponseT] class definition.

    The handler performs class-definition-time validation via __init_subclass__ to ensure:
    - The __call__ method exists and is properly implemented
    - The __call__ method is asynchronous (async def)
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
        Basic async handler:
            ```python
            from dataclasses import dataclass
            from pymediate import Request, RequestHandler

            @dataclass
            class UserResponse:
                user_id: int
                username: str

            @dataclass
            class CreateUserRequest(Request[UserResponse]):
                username: str
                email: str

            class CreateUserHandler(RequestHandler[CreateUserRequest]):
                async def __call__(self, request: CreateUserRequest) -> UserResponse:
                    # Can use await in async handlers
                    user_id = await async_generate_id()
                    return UserResponse(user_id=user_id, username=request.username)
            ```

        Async handler with dependencies:
            ```python
            class CreateUserHandler(RequestHandler[CreateUserRequest]):
                def __init__(self, database: AsyncDatabase):
                    self.database = database

                async def __call__(self, request: CreateUserRequest) -> UserResponse:
                    user_id = await self.database.insert_user(
                        username=request.username,
                        email=request.email
                    )
                    return UserResponse(user_id=user_id, username=request.username)
            ```

    Note:
        For synchronous handlers, use `pymediate.sync.RequestHandler` instead.
        Validation occurs at class definition time. If your __call__ signature
        doesn't match expectations, you'll get a clear error message when the
        module is imported, not when the handler is invoked.

    Raises:
        InvalidHandlerSignatureError: If __call__ signature is invalid or not async.
        InvalidRequestTypeError: If request type doesn't inherit from Request.
        ResponseTypeMismatchError: If return type doesn't match expected response.

    See Also:
        - Request: Base request class
        - Mediator: Routes requests to async handlers
        - pymediate.sync.RequestHandler: Sync handler variant
        - pymediate.sync.Mediator: Sync mediator variant
    """

    _is_async = True  # Mark this as an asynchronous handler

    @abstractmethod
    async def __call__(self, request: RequestT) -> Any:
        """Handle the request asynchronously and return a response.

        This is an abstract method that must be implemented by all async RequestHandler
        subclasses, with the signature
        `async def __call__(self, request: RequestType) -> ResponseType: ...`

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
            class definition. This method must also be asynchronous (`async def`);
            for sync handlers, use `pymediate.sync.RequestHandler`.
        """
        ...
