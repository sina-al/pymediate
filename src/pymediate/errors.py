"""Custom exceptions for PyMediate with helpful error messages and documentation links."""

DOCS_URL = "https://sina-al.github.io/pymediate"


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
        >>> mediator.send(MyRequest())
        HandlerNotFoundError: No handler registered for request type 'MyRequest'
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
            "  1. Register a handler: resolver.register({request_type.__name__}, handler)\n"
            "  2. Ensure your DI container has a provider for this handler\n"
            "  3. Verify {request_type.__name__} inherits from Request[ResponseType]"
        )

        if available_handlers:
            handler_names = ", ".join(h.__name__ for h in available_handlers[:5])
            if len(available_handlers) > 5:
                handler_names += f", ... and {len(available_handlers) - 5} more"
            message += f"\n\n📋 Available handlers: {handler_names}"

        super().__init__(message, docs_path="guide/handlers")


class HandlerTypeMismatchError(PyMediateError):
    """Raised when a handler is registered for the wrong request type.

    This is a type-safety feature that prevents runtime errors by validating
    that handlers are registered with the correct request types.

    Example:
        >>> resolver.register(Request1, Handler2())  # Handler2 handles Request2!
        HandlerTypeMismatchError: Handler type mismatch
    """

    def __init__(self, handler_type: type, expected_request: type, actual_request: type):
        """Initialize handler type mismatch error.

        Args:
            handler_type: The handler class
            expected_request: The request type the handler actually handles
            actual_request: The request type it's being registered for
        """
        self.handler_type = handler_type
        self.expected_request = expected_request
        self.actual_request = actual_request

        message = (
            f"Handler type mismatch: {handler_type.__name__} is designed to handle "
            f"'{expected_request.__name__}', but you're trying to register it for "
            f"'{actual_request.__name__}'\n\n"
            "💡 Solution: Ensure the handler is registered with the correct request type:\n"
            f"  resolver.register({expected_request.__name__}, {handler_type.__name__}())"
        )

        super().__init__(message, docs_path="guide/resolvers")


class InvalidHandlerSignatureError(PyMediateError):
    """Raised when a handler has an invalid __call__ signature.

    Handlers must have a __call__ method with exactly one parameter (the request)
    and a return type annotation matching the expected response type.

    Example:
        >>> class BadHandler(Handler[MyRequest]):
        ...     def __call__(self):  # Missing request parameter!
        ...         pass
        InvalidHandlerSignatureError: Invalid handler signature
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
            "  ❌ Wrong parameter type annotation\n"
            "  ❌ Missing or wrong return type annotation\n"
            "  ❌ Extra parameters (only 'self' and 'request' allowed)"
        )

        super().__init__(message, docs_path="guide/handlers")


class InvalidRequestTypeError(PyMediateError):
    """Raised when a request doesn't properly inherit from Request[ResponseType].

    All request classes must inherit from Request[ResponseType] to specify
    their expected response type.

    Example:
        >>> class MyRequest:  # Missing Request[ResponseType] inheritance!
        ...     pass
        >>> class MyHandler(Handler[MyRequest]):
        ...     pass
        InvalidRequestTypeError: Invalid request type
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

        super().__init__(message, docs_path="guide/requests-responses")


class DIContainerError(PyMediateError):
    """Raised when there's an issue with the DI container configuration.

    This can happen when:
    1. A provider is missing from the container
    2. Provider type inspection fails
    3. Container resolution fails

    Example:
        >>> from pymediate.service_providers import DependencyInjectorServiceProvider
        >>> provider = DependencyInjectorServiceProvider(container)
        >>> mediator.send(MyRequest())
        DIContainerError: Failed to resolve handler from DI container
    """

    def __init__(self, request_type: type, reason: str):
        """Initialize DI container error.

        Args:
            request_type: The request type being resolved
            reason: Why the container failed to resolve the handler
        """
        self.request_type = request_type
        self.reason = reason

        message = (
            f"Failed to resolve handler for '{request_type.__name__}' from DI container\n\n"
            f"Reason: {reason}\n\n"
            "💡 Common solutions:\n"
            "  1. Add a provider to your container:\n"
            "     container = Container()\n"
            "     container.my_handler = providers.Factory(MyHandler, ...)\n\n"
            "  2. Ensure the provider returns a Handler instance\n\n"
            "  3. Check that dependencies are properly configured"
        )

        super().__init__(message, docs_path="guide/di-integration")


class ResponseTypeMismatchError(PyMediateError):
    """Raised when a handler returns the wrong response type.

    This is caught at class definition time through signature validation,
    but can also occur at runtime if response types are incorrect.

    Example:
        >>> class MyHandler(Handler[MyRequest]):
        ...     def __call__(self, request: MyRequest) -> WrongResponse:  # Should be MyResponse!
        ...         return WrongResponse()
        ResponseTypeMismatchError: Response type mismatch
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

        super().__init__(message, docs_path="guide/handlers")
