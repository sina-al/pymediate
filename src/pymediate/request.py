"""Request base class for the mediator pattern."""

from typing import Any

from pymediate.registry import _REQUEST_REGISTRY


class Request[ResponseT]:
    """Base request class with generic response type.

    All requests should inherit from Request[ResponseType] to specify their
    response type. This works seamlessly with dataclasses and any other Python class.

    Example with dataclasses:
        from dataclasses import dataclass

        @dataclass
        class UserCreatedResponse:
            user_id: int
            username: str

        @dataclass
        class CreateUserRequest(Request[UserCreatedResponse]):
            username: str
            email: str

    Example with regular classes:
        class UserCreatedResponse:
            def __init__(self, user_id: int):
                self.user_id = user_id

        class CreateUserRequest(Request[UserCreatedResponse]):
            def __init__(self, name: str, email: str):
                self.name = name
                self.email = email

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
