"""Request base class and decorator for the mediator pattern."""

from typing import Any

from pymediate.registry import _REQUEST_REGISTRY


def request[ResponseT](response_type: type[ResponseT]) -> Any:
    """Decorator to mark a class as a request with its response type.

    This is especially useful with dataclasses where you want both
    request and response to be dataclasses without inheritance.

    Example:
        from dataclasses import dataclass
        from pymediate import request

        @dataclass
        class UserResponse:
            user_id: int
            username: str

        @request(UserResponse)
        @dataclass
        class CreateUserRequest:
            username: str
            email: str

        # Now CreateUserRequest is registered with UserResponse
    """

    def decorator(cls: type) -> type:
        """Register the class as a request with the given response type."""
        _REQUEST_REGISTRY[cls] = response_type
        return cls

    return decorator


class Request[ResponseT]:
    """Base request class with generic response type.

    You can either:
    1. Inherit from Request[ResponseType] (generic syntax)
    2. Use @request(ResponseType) decorator (cleaner for dataclasses)

    Example with inheritance:
        class UserCreatedResponse:
            def __init__(self, user_id: int):
                self.user_id = user_id

        class CreateUserRequest(Request[UserCreatedResponse]):
            def __init__(self, name: str, email: str):
                self.name = name
                self.email = email

    Example with decorator (recommended for dataclasses):
        @dataclass
        class UserResponse:
            user_id: int
            username: str

        @request(UserResponse)
        @dataclass
        class CreateUserRequest:
            username: str
            email: str

    The response type is automatically registered and can be retrieved
    for runtime validation and type checking.
    """

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Register the response type when a Request subclass is created."""
        super().__init_subclass__(**kwargs)

        # Extract the response type from __orig_bases__
        if hasattr(cls, "__orig_bases__"):
            for base in cls.__orig_bases__:
                # Check if this is Request[SomeType]
                if hasattr(base, "__origin__") and base.__origin__ is Request:
                    if hasattr(base, "__args__") and base.__args__:
                        response_type = base.__args__[0]
                        _REQUEST_REGISTRY[cls] = response_type
                        break
