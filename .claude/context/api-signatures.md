<!-- GENERATED FILE — do not hand-edit. -->
<!-- Regenerate with `uv run poe context:update` (see scripts/update_context.py). -->
<!-- Imported into .claude/CLAUDE.md via @context/api-signatures.md. -->

# API Signatures (generated)

Signatures-only blueprint of pymediate's public API. Full docstrings, guides, and examples live in `docs/content/docs/` and https://pymediate.sina-al.uk/.

### `pymediate`

```python
# Re-exports: Request, RequestHandler, Mediator, Event, EventHandler, StreamRequest, StreamRequestHandler, ServiceProvider, Services, ServiceNotFoundError, PipelineBehavior, Next, PyMediateError, HandlerNotFoundError, HandlerAlreadyRegisteredError, InvalidHandlerSignatureError, InvalidRequestTypeError, InvalidEventTypeError, InvalidStreamRequestTypeError, ResponseTypeMismatchError
```

### `pymediate.request`

```python
class Request:
    """Base request class with generic response type parameter."""
    ...
```

### `pymediate.event`

```python
class Event:
    """Base class for events published to zero or more handlers."""
    ...

class EventHandler(EventHandlerBaseMixin[EventT], ABC):
    """Abstract base class for asynchronous event handlers."""
    @abstractmethod
    async def __call__(self, event: EventT) -> None:
        """Handle the published event asynchronously."""
        ...
```

### `pymediate.handler`

```python
class RequestHandler(HandlerBaseMixin[RequestT], ABC):
    """Abstract base handler class for asynchronous request processing."""
    @abstractmethod
    async def __call__(self, request: RequestT) -> Any:
        """Handle the request asynchronously and return a response."""
        ...
```

### `pymediate.mediator`

```python
class Mediator(MediatorMixin):
    """Routes requests to their async handlers using a service provider."""
    async def send(self, request: Request[ResponseT]) -> ResponseT:
        """Send a request and await the typed response from its handler."""
        ...
    def stream(self, request: StreamRequest[ChunkT]) -> AsyncIterator[ChunkT]:
        """Route a stream request to its handler and return the async chunk stream."""
        ...
    async def publish(self, event: Event) -> None:
        """Publish an event to every async handler subscribed to its type."""
        ...
```

### `pymediate.pipeline`

```python
class PipelineBehavior(ABC):
    """Abstract base class for asynchronous pipeline behaviors that wrap request processing."""
    @classmethod
    def should_apply(cls, request: Request[Any]) -> bool:
        """Determine if this behavior should apply to the given request."""
        ...
    @abstractmethod
    async def __call__(self, request: RequestT, next: Next[Any]) -> Any:
        """Execute the behavior's async logic and await next to continue the pipeline."""
        ...
```

### `pymediate.service`

```python
class ServiceNotFoundError(Exception):
    """Raised when a requested service type is not registered."""
    def __init__(self, service_type: type, available_types: list[type]) -> None:
        """Create the error for a service type that has no registered instance."""
        ...

class ServiceProvider(Protocol):
    """Protocol for resolving registered service instances."""
    def get(self, service_type: type[ServiceT]) -> ServiceT:
        """Get the first registered instance of the exact type."""
        ...
    def get_all(self, service_type: type[ServiceT]) -> Sequence[ServiceT]:
        """Get all instances of the type, including subclasses."""
        ...
    def has(self, service_type: type) -> bool:
        """Check whether any instance of the exact type is registered."""
        ...
    def get_all_types(self) -> tuple[type, ...]:
        """Get every exact type that has at least one registered instance."""
        ...

class Services:
    """Mutable collection for registering service instances."""
    def __init__(self) -> None:
        """Create an empty service collection."""
        ...
    def add(self, instance: object) -> Services:
        """Register a service instance."""
        ...
    def provider(self) -> ServiceProvider:
        """Build an immutable ServiceProvider from the currently registered services."""
        ...
    def clear(self) -> None:
        """Remove all registered services from this collection."""
        ...
```

### `pymediate.errors`

```python
class PyMediateError(Exception):
    """Base exception for all PyMediate errors."""
    def __init__(self, message: str, docs_path: str | None = None):
        """Initialize the error with a message and optional docs link."""
        ...

class HandlerNotFoundError(PyMediateError):
    """Raised when no handler is registered for a request type."""
    def __init__(self, request_type: type, available_handlers: list[type] | None = None):
        """Initialize handler not found error."""
        ...

class InvalidHandlerSignatureError(PyMediateError):
    """Raised when a handler has an invalid __call__ signature."""
    def __init__(self, handler_type: type, issue: str):
        """Initialize invalid handler signature error."""
        ...

class InvalidRequestTypeError(PyMediateError):
    """Raised when a request doesn't properly inherit from Request[ResponseType]."""
    def __init__(self, request_type: type):
        """Initialize invalid request type error."""
        ...

class InvalidEventTypeError(PyMediateError):
    """Raised when an event handler's type parameter doesn't inherit from Event."""
    def __init__(self, event_type: type):
        """Initialize the error for a type parameter that isn't an Event subclass."""
        ...

class InvalidStreamRequestTypeError(PyMediateError):
    """Raised when a stream handler's type parameter doesn't inherit from StreamRequest."""
    def __init__(self, stream_request_type: type):
        """Initialize the error for a type parameter that isn't a StreamRequest subclass."""
        ...

class ResponseTypeMismatchError(PyMediateError):
    """Raised when a handler returns the wrong response type."""
    def __init__(self, handler_type: type, expected_type: type, actual_type: type):
        """Initialize response type mismatch error."""
        ...

class HandlerAlreadyRegisteredError(PyMediateError):
    """Raised when attempting to register a second handler for a request type."""
    def __init__(self, request_type: type, existing_handler: type, new_handler: type, existing_location: str | None = None):
        """Initialize handler already registered error."""
        ...
```

### `pymediate.providers.dependency_injector`

```python
class DependencyInjectorServiceProvider:
    """ServiceProvider backed by a Dependency Injector container."""
    def __init__(self, container: containers.Container, *, provider_types: Mapping[providers.Provider[Any], type[Any]] | None = None) -> None:
        """Index services declared by a Dependency Injector container."""
        ...
    def get(self, service_type: type[ServiceT]) -> ServiceT:
        """Get the first registered instance of the exact type."""
        ...
    def get_all(self, service_type: type[Any]) -> Sequence[Any]:
        """Get all instances of the type, including subclasses, in declaration order."""
        ...
    def has(self, service_type: type[Any]) -> bool:
        """Check whether any instance of the exact type is registered."""
        ...
    def get_all_types(self) -> tuple[type[Any], ...]:
        """Get every exact type that has at least one registered instance."""
        ...
```

### `pymediate.sync`

```python
# Re-exports: Request, RequestHandler, Mediator, Event, EventHandler, StreamRequest, StreamRequestHandler, ServiceProvider, Services, ServiceNotFoundError, PipelineBehavior, Next, PyMediateError, HandlerNotFoundError, HandlerAlreadyRegisteredError, InvalidHandlerSignatureError, InvalidRequestTypeError, InvalidEventTypeError, InvalidStreamRequestTypeError, ResponseTypeMismatchError
```

### `pymediate.sync.event`

```python
class EventHandler(EventHandlerBaseMixin[EventT], ABC):
    """Abstract base class for synchronous event handlers."""
    @abstractmethod
    def __call__(self, event: EventT) -> None:
        """Handle the published event."""
        ...
```

### `pymediate.sync.handler`

```python
class RequestHandler(HandlerBaseMixin[RequestT], ABC):
    """Abstract base handler class for synchronous request processing."""
    @abstractmethod
    def __call__(self, request: RequestT) -> Any:
        """Handle the request and return a response."""
        ...
```

### `pymediate.sync.mediator`

```python
class Mediator(MediatorMixin):
    """Routes requests to their handlers using a service provider."""
    def send(self, request: Request[ResponseT]) -> ResponseT:
        """Send a request and get the typed response from its handler."""
        ...
    def stream(self, request: StreamRequest[ChunkT]) -> Iterator[ChunkT]:
        """Route a stream request to its handler and return the chunk stream."""
        ...
    def publish(self, event: Event) -> None:
        """Publish an event to every handler subscribed to its type."""
        ...
```

### `pymediate.sync.pipeline`

```python
class PipelineBehavior(ABC):
    """Abstract base class for pipeline behaviors that wrap request processing."""
    @classmethod
    def should_apply(cls, request: Request[Any]) -> bool:
        """Determine if this behavior should apply to the given request."""
        ...
    @abstractmethod
    def __call__(self, request: RequestT, next: Next[Any]) -> Any:
        """Execute the behavior's logic and call next to continue the pipeline."""
        ...
```
