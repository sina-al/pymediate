"""PyMediate exceptions and their documentation links."""

DOCS_URL = "https://pymediate.sina-al.uk"


def _type_name(value: object) -> str:
    """Return a readable name for a class or another type annotation."""
    if isinstance(value, type):
        return value.__name__
    return str(value)


class PyMediateError(Exception):
    """Base exception for PyMediate validation, registration, and dispatch errors.

    ``ServiceNotFoundError`` is separate and inherits directly from ``Exception``.
    Subscriber failures from ``publish()`` may use Python exception groups;
    fatal base exceptions can propagate directly.
    """

    def __init__(self, message: str, docs_path: str | None = None):
        """Initialize the error with a message and optional docs link.

        Args:
            message: The error message
            docs_path: Optional path to relevant documentation, without a leading slash.
        """
        self.docs_path = docs_path
        full_message = message
        if docs_path:
            full_message = f"{message}\n\nDocumentation: {DOCS_URL}/{docs_path}"
        super().__init__(full_message)


class HandlerNotFoundError(PyMediateError):
    """Raised when no handler is registered for a request type.

    Request and stream handler classes register when Python defines them. This
    error means the exact request class has no handler class in that registry.
    A registered handler class whose instance cannot be resolved instead raises
    ``ServiceNotFoundError``.
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
            "Checks:\n"
            "  1. Define a handler for this exact request type\n"
            "  2. Import the module containing that handler before dispatch\n"
            "  3. Use send() for Request and stream() for StreamRequest"
        )

        if available_handlers:
            handler_names = ", ".join(h.__name__ for h in available_handlers[:5])
            if len(available_handlers) > 5:
                handler_names += f", ... and {len(available_handlers) - 5} more"
            message += f"\n\nRequest types with handlers: {handler_names}"

        super().__init__(
            message,
            docs_path="docs/guide/troubleshooting#handlernotfounderror",
        )


class InvalidHandlerSignatureError(PyMediateError):
    """Raised when a handler has an invalid __call__ signature.

    Request, notification, and stream handlers each validate the parameter annotation,
    return annotation, and synchronous, asynchronous, or generator form required
    by their handler base class. ``issue`` describes the failed part of that
    contract.
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
            "Handler declaration checks:\n"
            "  - __call__ accepts one message parameter in addition to self\n"
            "  - the parameter annotation is the exact declared message class\n"
            "  - the return annotation matches the handler contract\n"
            "  - __call__ uses the required sync, async, or generator form"
        )

        super().__init__(
            message,
            docs_path="docs/guide/troubleshooting#invalidhandlersignatureerror",
        )


class InvalidRequestTypeError(PyMediateError):
    """Raised when a request handler's type parameter has no declared response type.

    A request used with ``RequestHandler`` must inherit from
    ``Request[ResponseType]`` so its expected response type is recorded.
    """

    def __init__(self, request_type: type):
        """Initialize invalid request type error.

        Args:
            request_type: The type that does not declare a request response type.
        """
        self.request_type = request_type

        request_name = _type_name(request_type)
        message = (
            f"Request type '{request_name}' must inherit from Request[ResponseType]\n\n"
            "Expected request definition:\n"
            "  @dataclass\n"
            "  class MyRequest(Request[MyResponse]):\n"
            "      field1: str\n"
            "      field2: int\n\n"
            "Request[ResponseType] records the expected response for static\n"
            "inference and handler return-annotation validation."
        )

        super().__init__(
            message,
            docs_path="docs/guide/troubleshooting#invalid-request-notification-or-stream-types",
        )


class InvalidNotificationTypeError(PyMediateError):
    """Raised when a notification handler's type parameter doesn't inherit from Notification.

    All notification classes must inherit from Notification so they can be published via
    Mediator.publish().
    """

    def __init__(self, notification_type: type):
        """Initialize the error for a type parameter that isn't a Notification subclass.

        Args:
            notification_type: The type that doesn't inherit from Notification
        """
        self.notification_type = notification_type

        name = getattr(notification_type, "__name__", str(notification_type))
        message = (
            f"Notification type '{name}' must inherit from Notification\n\n"
            "Expected notification definition:\n"
            "  @dataclass\n"
            f"  class {name}(Notification):\n"
            "      field1: str\n"
            "      field2: int\n\n"
            "A Notification subclass can be passed to mediator.publish() and named in\n"
            "NotificationHandler[...]."
        )

        super().__init__(
            message,
            docs_path="docs/guide/troubleshooting#invalid-request-notification-or-stream-types",
        )


class InvalidStreamRequestTypeError(PyMediateError):
    """Raised when a stream handler's type parameter has no declared chunk type.

    A request used with ``StreamRequestHandler`` must inherit from
    ``StreamRequest[ChunkType]`` so its yielded element type is recorded.
    """

    def __init__(self, stream_request_type: type):
        """Initialize the error for a type with no StreamRequest chunk declaration.

        Args:
            stream_request_type: The type that does not declare a stream chunk type.
        """
        self.stream_request_type = stream_request_type

        name = getattr(stream_request_type, "__name__", str(stream_request_type))
        message = (
            f"Stream request type '{name}' must inherit from StreamRequest[ChunkType]\n\n"
            "Expected stream request definition:\n"
            "  @dataclass\n"
            f"  class {name}(StreamRequest[str]):\n"
            "      field1: str\n"
            "      field2: int\n\n"
            "StreamRequest[ChunkType] records the element type yielded by its\n"
            "handler and returned by mediator.stream()."
        )

        super().__init__(
            message,
            docs_path="docs/guide/troubleshooting#invalid-request-notification-or-stream-types",
        )


class ResponseTypeMismatchError(PyMediateError):
    """Raised when a request handler's return annotation names the wrong response type.

    PyMediate compares the handler's return annotation with the response type
    declared by its request when Python defines the handler class. It does not
    inspect the value returned later during dispatch.
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

        expected_name = _type_name(expected_type)
        actual_name = _type_name(actual_type)
        method_prefix = "async def" if getattr(handler_type, "_is_async", False) else "def"
        message = (
            f"Response type mismatch in {handler_type.__name__}\n\n"
            f"Expected: {expected_name}\n"
            f"Got: {actual_name}\n\n"
            "The return annotation must match Request[ResponseType]:\n"
            f"  class MyRequest(Request[{expected_name}]):\n"
            "      ...\n\n"
            f"  class MyHandler(RequestHandler[MyRequest]):\n"
            f"      {method_prefix} __call__(self, request: MyRequest) -> {expected_name}:\n"
            f"          return {expected_name}(...)"
        )

        super().__init__(message, docs_path="docs/guide/troubleshooting#responsetypemismatcherror")


class HandlerAlreadyRegisteredError(PyMediateError):
    """Raised when a second request or stream handler targets one request type.

    The process-wide registry stores one request or stream handler class for each
    exact request type. Notification handlers use a separate registry and may have several
    subscribers for one notification type.
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
            f"Handler already registered for '{request_type.__name__}'\n\n"
            f"Existing handler: {existing_handler.__name__}\n"
            f"Attempting to register: {new_handler.__name__}\n"
        )

        if existing_location:
            message += f"\nFirst handler was registered at:\n   {existing_location}\n"

        message += (
            "\nEach request type can have one request or stream handler.\n\n"
            "Solutions:\n"
            "  1. Remove one of the handler class definitions\n"
            "  2. Use different request types when the operations have different contracts\n"
            "  3. Compose the work behind one registered handler\n"
        )

        super().__init__(
            message, docs_path="docs/guide/troubleshooting#handleralreadyregisterederror"
        )


class InvalidPipelineBehaviorsError(PyMediateError):
    """Raised when a mediator's ``behaviors`` sequence is invalid at construction.

    The mediator validates the sequence once, when it is constructed: every entry
    must be a ``PipelineBehavior`` subclass of the mediator's variant (synchronous
    or asynchronous), must be registered with the service provider, and may be
    listed only once. ``issue`` describes the failed part of that contract.
    """

    def __init__(self, entry: object, issue: str):
        """Initialize the error for one invalid ``behaviors`` entry.

        Args:
            entry: The offending entry from the ``behaviors`` sequence.
            issue: Description of what's wrong with the entry.
        """
        self.entry = entry
        self.issue = issue

        message = (
            f"Invalid behaviors entry '{_type_name(entry)}': {issue}\n\n"
            "The behaviors sequence passed to Mediator(...) declares the pipeline:\n"
            "  - each entry is a PipelineBehavior subclass (a class, not an instance)\n"
            "  - of the mediator's variant (synchronous or asynchronous)\n"
            "  - registered with the service provider\n"
            "  - listed at most once\n\n"
            "Execution order is the sequence order - the first entry is outermost."
        )

        super().__init__(
            message, docs_path="docs/guide/troubleshooting#invalidpipelinebehaviorserror"
        )
