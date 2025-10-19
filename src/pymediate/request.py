"""Request base class for the mediator pattern."""

from typing import Any

from pymediate.registry import _REQUEST_REGISTRY


class Request[ResponseT]:
    """Base request class with generic response type parameter.

    All requests should inherit from `Request[ResponseType]` to specify their
    expected response type. This enables automatic type inference and runtime
    validation throughout the mediator pattern.

    The response type is automatically registered when a Request subclass is
    created via the __init_subclass__ hook, making it available for handler
    validation and type checking.

    This class works seamlessly with dataclasses, regular classes, and any
    Python class structure.

    Type Parameters:
        ResponseT: The type of response that handlers will return for this request.

    Examples:
        Using with dataclasses (recommended):
            ```python
            from dataclasses import dataclass

            @dataclass
            class UserCreatedResponse:
                user_id: int
                username: str

            @dataclass
            class CreateUserRequest(Request[UserCreatedResponse]):
                username: str
                email: str
            ```

        Using with regular classes:
            ```python
            class UserCreatedResponse:
                def __init__(self, user_id: int):
                    self.user_id = user_id

            class CreateUserRequest(Request[UserCreatedResponse]):
                def __init__(self, name: str, email: str):
                    self.name = name
                    self.email = email
            ```

    Note:
        The response type is extracted and registered automatically when the
        class is defined. This happens at import time, not at runtime, so
        there is no performance penalty for using this pattern.

    See Also:
        - Handler: Base handler class that processes requests
        - Mediator.send: Method that routes requests to handlers
    """

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Register the response type when a Request subclass is created.

        This hook is automatically called when a new Request subclass is defined.
        It extracts the response type from the generic type parameter and stores
        it in the global registry for later validation.

        Args:
            **kwargs: Additional keyword arguments passed to parent __init_subclass__.

        Note:
            This method is called automatically by Python when a subclass is created.
            You should not call this method directly.
        """
        super().__init_subclass__(**kwargs)

        if orig_bases := getattr(cls, "__orig_bases__", None):
            for base in orig_bases:
                if getattr(base, "__origin__", None) is Request:
                    if args := getattr(base, "__args__", None):
                        response_type = args[0]
                        _REQUEST_REGISTRY[cls] = response_type
                        break
