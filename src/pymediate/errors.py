"""Custom exceptions for PyMediate with helpful error messages and documentation links."""

DOCS_URL = "https://pymediate.sina-al.uk"


class PyMediateError(Exception):
    """Base exception for all PyMediate errors.

    All PyMediate exceptions inherit from this class, making it easy to
    catch any PyMediate-specific error.
    """

    def __init__(self, message: str, docs_path: str | None = None):
        """Initialize the error with a message and optional docs link.

        Args:
            message: The error message
            docs_path: Optional path to relevant documentation (e.g., "guide/handlers")
        """
        self.docs_path = docs_path
        full_message = message
        if docs_path:
            full_message = f"{message}\n\n📚 Learn more: {DOCS_URL}/{docs_path}"
        super().__init__(full_message)


class HandlerNotFoundError(PyMediateError):
    """Raised when no handler is registered for a request type.

    This typically happens when:
    1. You forgot to register a handler for the request
    2. You're using a DI container but the handler provider is missing
    3. The request type doesn't inherit from Request[ResponseType]

    Example:
        ```python
        mediator.send(MyRequest())
        # HandlerNotFoundError: No handler registered for request type 'MyRequest'
        ```
    """

    def __init__(self, request_type: type, available_handlers: list[type] | None = None):
        """Initialize handler not found error.

        Args:
            request_type: The request type that has no handler
            available_handlers: Optional list of registered request types
        """
        self.request_type = request_type
        self.available_handlers = available_handlers

        message = (
            f"No handler registered for request type '{request_type.__name__}'\n\n"
            "💡 Possible solutions:\n"
            "  1. Register a handler: services.add(your_handler_instance)\n"
            "  2. Ensure your DI container has a provider for this handler\n"
            f"  3. Verify {request_type.__name__} inherits from Request[ResponseType]"
        )

        if available_handlers:
            handler_names = ", ".join(h.__name__ for h in available_handlers[:5])
            if len(available_handlers) > 5:
                handler_names += f", ... and {len(available_handlers) - 5} more"
            message += f"\n\n📋 Available handlers: {handler_names}"

        super().__init__(
            message,
            docs_path="docs/advanced/troubleshooting#handlernotfounderror",
        )


class InvalidHandlerSignatureError(PyMediateError):
    """Raised when a handler has an invalid __call__ signature.

    Handlers must have a __call__ method with exactly one parameter (the request)
    and a return type annotation matching the expected response type. The request
    parameter must annotate the exact request class declared in Handler[...] —
    a base class or union is rejected, because dispatch is keyed by the exact
    request type.

    Example:
        ```python
        class BadHandler(Handler[MyRequest]):
            def __call__(self):  # Missing request parameter!
                pass
        # InvalidHandlerSignatureError: Invalid handler signature
        ```
    """

    def __init__(self, handler_type: type, issue: str):
        """Initialize invalid handler signature error.

        Args:
            handler_type: The handler class with invalid signature
            issue: Description of what's wrong with the signature
        """
        self.handler_type = handler_type
        self.issue = issue

        message = (
            f"Invalid handler signature in {handler_type.__name__}: {issue}\n\n"
            "✅ Correct handler signature:\n"
            "  class MyHandler(Handler[MyRequest]):\n"
            "      def __call__(self, request: MyRequest) -> MyResponse:\n"
            "          return MyResponse(...)\n\n"
            "Common mistakes:\n"
            "  ❌ Missing request parameter\n"
            "  ❌ Parameter not annotated with the exact request class\n"
            "     (a base class or union is rejected)\n"
            "  ❌ Missing or wrong return type annotation\n"
            "  ❌ Extra parameters (only 'self' and 'request' allowed)"
        )

        super().__init__(
            message,
            docs_path="docs/advanced/troubleshooting#invalidhandlersignatureerror",
        )


class InvalidRequestTypeError(PyMediateError):
    """Raised when a request doesn't properly inherit from Request[ResponseType].

    All request classes must inherit from Request[ResponseType] to specify
    their expected response type.

    Example:
        ```python
        class MyRequest:  # Missing Request[ResponseType] inheritance!
            pass

        class MyHandler(Handler[MyRequest]):
            pass
        # InvalidRequestTypeError: Invalid request type
        ```
    """

    def __init__(self, request_type: type):
        """Initialize invalid request type error.

        Args:
            request_type: The request type that doesn't inherit from Request
        """
        self.request_type = request_type

        message = (
            f"Request type '{request_type.__name__}' must inherit from Request[ResponseType]\n\n"
            "✅ Correct request definition:\n"
            "  @dataclass\n"
            "  class MyRequest(Request[MyResponse]):\n"
            "      field1: str\n"
            "      field2: int\n\n"
            "💡 The Request[ResponseType] inheritance tells PyMediate what type of\n"
            "   response to expect, enabling type-safe validation."
        )

        super().__init__(
            message,
            docs_path="docs/advanced/troubleshooting#invalidrequesttypeerror",
        )


class ResponseTypeMismatchError(PyMediateError):
    """Raised when a handler returns the wrong response type.

    This is caught at class definition time through signature validation,
    but can also occur at runtime if response types are incorrect.

    Example:
        ```python
        class MyHandler(Handler[MyRequest]):
            def __call__(self, request: MyRequest) -> WrongResponse:  # Should be MyResponse
                return WrongResponse()
        # ResponseTypeMismatchError: Response type mismatch
        ```
    """

    def __init__(self, handler_type: type, expected_type: type, actual_type: type):
        """Initialize response type mismatch error.

        Args:
            handler_type: The handler class
            expected_type: The expected response type
            actual_type: The actual response type annotation
        """
        self.handler_type = handler_type
        self.expected_type = expected_type
        self.actual_type = actual_type

        message = (
            f"Response type mismatch in {handler_type.__name__}\n\n"
            f"Expected: {expected_type.__name__}\n"
            f"Got: {actual_type.__name__}\n\n"
            "💡 The response type must match what's declared in Request[ResponseType]:\n"
            f"  class MyRequest(Request[{expected_type.__name__}]):\n"
            "      ...\n\n"
            f"  class MyHandler(Handler[MyRequest]):\n"
            f"      def __call__(self, request: MyRequest) -> {expected_type.__name__}:\n"
            f"          return {expected_type.__name__}(...)"
        )

        super().__init__(
            message, docs_path="docs/advanced/troubleshooting#responsetypemismatcherror"
        )


class HandlerAlreadyRegisteredError(PyMediateError):
    """Raised when attempting to register a second handler for a request type.

    PyMediate enforces a strict one-handler-per-request-type policy to prevent
    ambiguity and accidental registration conflicts. Each request type can only
    have a single handler.

    Example:
        ```python
        class FirstHandler(Handler[MyRequest]):
            pass

        class SecondHandler(Handler[MyRequest]):  # Error!
            pass
        # HandlerAlreadyRegisteredError: Handler already registered for 'MyRequest'
        ```
    """

    def __init__(
        self,
        request_type: type,
        existing_handler: type,
        new_handler: type,
        existing_location: str | None = None,
    ):
        """Initialize handler already registered error.

        Args:
            request_type: The request type that already has a handler
            existing_handler: The handler that was registered first
            new_handler: The handler attempting to register now
            existing_location: Optional file/line where first handler was registered
        """
        self.request_type = request_type
        self.existing_handler = existing_handler
        self.new_handler = new_handler
        self.existing_location = existing_location

        message = (
            f"⚠️  Handler already registered for '{request_type.__name__}'\n\n"
            f"Existing handler: {existing_handler.__name__}\n"
            f"Attempting to register: {new_handler.__name__}\n"
        )

        if existing_location:
            message += f"\n📍 First handler was registered at:\n   {existing_location}\n"

        message += (
            "\n💡 Each request type can only have ONE handler.\n\n"
            "Solutions:\n"
            "  1. Remove one of the handler class definitions\n"
            "  2. Use different request types for different behaviors:\n"
            f"     class {request_type.__name__}V1(Request[Response]): ...\n"
            f"     class {request_type.__name__}V2(Request[Response]): ...\n\n"
            "  3. Compose handlers to combine behaviors:\n"
            "     class ComposedHandler(Handler[MyRequest]):\n"
            "         def __call__(self, request):\n"
            "             # Combine both behaviors here\n"
            "             ...\n"
        )

        super().__init__(
            message, docs_path="docs/advanced/troubleshooting#handleralreadyregisterederror"
        )
