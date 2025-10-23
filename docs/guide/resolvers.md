# Resolvers

Resolvers are the dependency injection mechanism in PyMediate. They're responsible for providing handler instances when the mediator needs to process a request.

## What is a Resolver?

A resolver implements a simple contract: given a request type, return a handler instance that can process that request. This abstraction allows PyMediate to work with any dependency injection framework or pattern you prefer.

```python
class Resolver(Protocol):
    def resolve(self, request_class: type[RequestType]) -> Handler[RequestType]:
        """Resolve and return a handler instance for the given request type."""
        ...
```

## Why Resolvers?

Resolvers solve a critical problem in application architecture: **how do you get handler instances with their dependencies?**

Without a resolver, you'd have to manually wire up every handler:

```python
# Without resolver - manual wiring
database = Database()
email_service = EmailService()
user_handler = CreateUserHandler(database, email_service)

# Have to manage this for every handler!
```

With a resolver, dependencies are managed automatically:

```python
# With resolver - automatic dependency injection
mediator = Mediator(resolver)
response = mediator.send(CreateUserRequest(...))
# Handler is resolved with all its dependencies automatically!
```

## Built-in Resolvers

### SimpleResolver

The `SimpleResolver` is a basic dict-based resolver perfect for:

- Simple applications without complex dependencies
- Testing
- Learning PyMediate
- Singleton-style handler instances

**Example:**

```python
from pymediate import SimpleResolver, Mediator, Handler, Request

# Define your request/response
class CreateUserRequest(Request[UserCreated]):
    def __init__(self, username: str):
        self.username = username

class CreateUserHandler(Handler[CreateUserRequest]):
    def __call__(self, request: CreateUserRequest) -> UserCreated:
        # Handle the request
        return UserCreated(user_id=1, username=request.username)

# Set up resolver
resolver = SimpleResolver()
resolver.register(CreateUserHandler())

# Use it
mediator = Mediator(resolver)
result = mediator.send(CreateUserRequest("alice"))
```

**Type Safety:**

SimpleResolver validates handlers at registration time:

```python
# This will raise HandlerTypeMismatchError!
resolver.register(WrongHandler())  # Wrong handler type
```

**Pre-populating:**

```python
# Create with handlers already registered
resolver = SimpleResolver(handlers={
    CreateUserRequest: CreateUserHandler(),
    SendEmailRequest: SendEmailHandler(),
})
```

### DependencyInjectorResolver

The `DependencyInjectorResolver` integrates with the [dependency-injector](https://python-dependency-injector.ets-labs.org/) library for complex applications with many dependencies.

**Key Features:**

- **Type Inspection**: No naming conventions required - uses type metadata
- **Automatic Discovery**: Scans your container and finds handlers automatically
- **Provider Support**: Works with Factory, Singleton, and other providers
- **Lazy Loading**: Handlers are created only when needed

**Basic Setup:**

```python
from dependency_injector import containers, providers
from pymediate import DependencyInjectorResolver, Mediator

class AppContainer(containers.DeclarativeContainer):
    # Infrastructure
    database = providers.Singleton(Database, connection_string="...")
    email_service = providers.Singleton(EmailService, api_key="...")

    # Handlers - can have ANY name, no conventions!
    user_creator = providers.Factory(
        CreateUserHandler,
        database=database,
        email=email_service
    )

    # Mediator setup
    __self__ = providers.Self()
    mediator = providers.Singleton(
        Mediator,
        resolver=providers.Singleton(
            DependencyInjectorResolver,
            container=__self__
        )
    )

# Use it
container = AppContainer()
mediator = container.mediator()
result = mediator.send(CreateUserRequest("alice"))
```

## Singleton vs Factory Providers

Understanding when to use Singleton vs Factory providers is crucial for correct behavior.

### Singleton Providers

**Use When:** The handler should be created once and reused for all requests.

**Characteristics:**
- Single instance across the application lifetime
- State is preserved between requests
- More memory efficient for stateless handlers

**Example:**

```python
class ReadUserHandler(Handler[ReadUserRequest]):
    """Stateless handler - safe as singleton"""

    def __init__(self, database: Database):
        self.database = database

    def __call__(self, request: ReadUserRequest) -> UserData:
        return self.database.get_user(request.user_id)

# Singleton - one instance reused
container.read_user_handler = providers.Singleton(
    ReadUserHandler,
    database=container.database
)
```

**When Safe:**
- Handler has no mutable state
- Handler doesn't store request-specific data
- Dependencies are thread-safe

**When Dangerous:**

```python
class DangerousHandler(Handler[MyRequest]):
    def __init__(self):
        self.request_count = 0  # Shared state across requests!

    def __call__(self, request: MyRequest) -> MyResponse:
        self.request_count += 1  # Race condition in concurrent scenarios!
        return MyResponse(count=self.request_count)
```

### Factory Providers

**Use When:** You need a fresh handler instance for each request.

**Characteristics:**
- New instance created per request
- No shared state between requests
- Safer for stateful handlers
- Slightly higher memory overhead

**Example:**

```python
class StatefulHandler(Handler[ProcessRequest]):
    """Stateful handler - needs fresh instance"""

    def __init__(self, cache: Cache):
        self.cache = cache
        self.processed_items = []  # Instance-specific state

    def __call__(self, request: ProcessRequest) -> ProcessResult:
        # Safe - each request gets its own handler instance
        self.processed_items.append(request.item)
        result = self.cache.process(self.processed_items)
        return ProcessResult(result=result)

# Factory - new instance per request
container.process_handler = providers.Factory(
    StatefulHandler,
    cache=container.cache
)
```

**Decision Matrix:**

| Handler Type | Provider Type | Reason |
|-------------|--------------|--------|
| Stateless, no instance variables | Singleton | Memory efficient, safe |
| Uses only injected dependencies | Singleton | Dependencies manage their own state |
| Has mutable instance state | Factory | Avoid shared state bugs |
| Accumulates data during processing | Factory | Each request needs clean slate |
| Used in async/concurrent context | Factory | Avoid race conditions |

## How Type Inspection Works

PyMediate's DI resolver doesn't rely on naming conventions. Instead, it uses **type introspection**:

```python
# During container scan:
# 1. Call each provider to get an instance
instance = provider()

# 2. Check if it's a Handler
if isinstance(instance, Handler):
    # 3. Extract the request type from the Handler class
    request_type = type(instance).get_request_type()

    # 4. Map request_type -> provider
    handler_providers[request_type] = provider
```

This means your providers can have **any name**:

```python
class AppContainer(containers.DeclarativeContainer):
    # All of these work - name doesn't matter!
    user_creation_service = providers.Factory(CreateUserHandler, ...)
    make_user = providers.Factory(CreateUserHandler, ...)
    x = providers.Factory(CreateUserHandler, ...)
    handler_42 = providers.Factory(CreateUserHandler, ...)
```

## Implementing a Custom Resolver

You can implement your own resolver for custom DI frameworks or patterns.

### The Resolver Protocol

```python
from typing import Protocol, TypeVar

RequestType = TypeVar("RequestType")

class Resolver(Protocol):
    def resolve(self, request_class: type[RequestType]) -> Handler[RequestType]:
        """Resolve and return a handler instance for the given request type."""
        ...
```

### Example: Service Locator Pattern

```python
class ServiceLocatorResolver:
    """Resolver using the service locator pattern."""

    def __init__(self):
        self._factories: dict[type, callable] = {}

    def register_factory(self, request_type: type, factory: callable):
        """Register a factory function for a request type."""
        self._factories[request_type] = factory

    def resolve(self, request_class: type) -> Handler:
        """Resolve by calling the registered factory."""
        if request_class not in self._factories:
            raise HandlerNotFoundError(
                request_class,
                list(self._factories.keys())
            )

        factory = self._factories[request_class]
        return factory()  # Call factory to create handler

# Usage
resolver = ServiceLocatorResolver()
resolver.register_factory(
    CreateUserRequest,
    lambda: CreateUserHandler(database=get_database())
)

mediator = Mediator(resolver)
```

### Example: Django Integration

```python
class DjangoResolver:
    """Resolver that uses Django's app registry."""

    def __init__(self):
        self._handlers = self._discover_handlers()

    def _discover_handlers(self) -> dict[type, type]:
        """Discover handlers from installed Django apps."""
        handlers = {}

        for app_config in apps.get_app_configs():
            # Look for handlers module in each app
            try:
                handlers_module = import_module(f'{app_config.name}.handlers')

                for name in dir(handlers_module):
                    obj = getattr(handlers_module, name)

                    if isinstance(obj, type) and issubclass(obj, Handler):
                        request_type = obj.get_request_type()
                        if request_type:
                            handlers[request_type] = obj
            except ImportError:
                continue

        return handlers

    def resolve(self, request_class: type) -> Handler:
        """Resolve handler and instantiate with Django dependencies."""
        if request_class not in self._handlers:
            raise HandlerNotFoundError(
                request_class,
                list(self._handlers.keys())
            )

        handler_class = self._handlers[request_class]

        # Instantiate with Django-specific dependencies
        # Could use Django's dependency injection if available
        return handler_class()
```

### Example: FastAPI Depends Integration

```python
from fastapi import Depends

class FastAPIResolver:
    """Resolver that works with FastAPI's dependency injection."""

    def __init__(self, app):
        self.app = app
        self._handler_factories = {}

    def register(self, request_type: type, handler_factory):
        """Register a handler factory (can use Depends)."""
        self._handler_factories[request_type] = handler_factory

    def resolve(self, request_class: type) -> Handler:
        if request_class not in self._handler_factories:
            raise HandlerNotFoundError(
                request_class,
                list(self._handler_factories.keys())
            )

        factory = self._handler_factories[request_class]
        return factory()

# Usage with FastAPI
def get_database():
    return Database()

def get_email_service():
    return EmailService()

def create_user_handler_factory(
    db: Database = Depends(get_database),
    email: EmailService = Depends(get_email_service)
):
    return CreateUserHandler(db, email)

resolver = FastAPIResolver(app)
resolver.register(CreateUserRequest, create_user_handler_factory)
```

## Common Patterns

### Scoped Resolvers (Request Scope)

For web applications, you often want request-scoped dependencies:

```python
from contextvars import ContextVar

# Request-scoped context
_current_request_id: ContextVar[str] = ContextVar('request_id')

class ScopedResolver:
    """Resolver with request scope support."""

    def __init__(self, container):
        self.container = container

    def resolve(self, request_class: type) -> Handler:
        # Create a new scope for this request
        request_id = _current_request_id.get()

        # Use container's scoped provider
        return self.container.handlers[request_class](
            request_id=request_id
        )
```

### Lazy Handler Loading

Defer handler creation until first use:

```python
class LazyResolver:
    """Resolver that loads handlers lazily."""

    def __init__(self):
        self._handler_cache = {}
        self._factories = {}

    def register_factory(self, request_type: type, factory: callable):
        self._factories[request_type] = factory

    def resolve(self, request_class: type) -> Handler:
        # Check cache first
        if request_class not in self._handler_cache:
            # Create and cache
            factory = self._factories[request_class]
            self._handler_cache[request_class] = factory()

        return self._handler_cache[request_class]
```

## Best Practices

### 1. Choose the Right Resolver

- **SimpleResolver**: Simple apps, prototypes, tests
- **DI Resolver**: Production apps with complex dependencies
- **Custom Resolver**: Framework-specific integrations

### 2. Handler Lifecycle

Consider handler lifecycle carefully:

```python
# Singleton: One instance forever
container.handler = providers.Singleton(MyHandler)

# Factory: New instance per mediator.send()
container.handler = providers.Factory(MyHandler)

# Scoped: New instance per scope (e.g., HTTP request)
container.handler = providers.Singleton(
    MyHandler,
    scope=RequestScope
)
```

### 3. Error Handling

Always handle `HandlerNotFoundError`:

```python
from pymediate import HandlerNotFoundError

try:
    result = mediator.send(request)
except HandlerNotFoundError as e:
    # Log the error with helpful context
    logger.error(
        f"No handler for {type(request).__name__}. "
        f"Available: {e.available_handlers}"
    )
    # Re-raise or handle gracefully
    raise
```

### 4. Testing Resolvers

Use SimpleResolver for tests:

```python
def test_user_creation():
    # Simple setup for tests
    resolver = SimpleResolver()
    resolver.register(
        CreateUserRequest,
        CreateUserHandler(FakeDatabase())
    )

    mediator = Mediator(resolver)
    result = mediator.send(CreateUserRequest("test"))

    assert result.username == "test"
```

### 5. Container Organization

Organize your DI container logically:

```python
class AppContainer(containers.DeclarativeContainer):
    # Configuration
    config = providers.Configuration()

    # Infrastructure layer
    database = providers.Singleton(Database, ...)
    cache = providers.Singleton(Redis, ...)
    email = providers.Singleton(EmailService, ...)

    # Application layer - Handlers
    create_user = providers.Factory(
        CreateUserHandler,
        database=database,
        email=email
    )

    send_email = providers.Factory(
        SendEmailHandler,
        email=email
    )

    # Mediator
    __self__ = providers.Self()
    mediator = providers.Singleton(
        Mediator,
        resolver=providers.Singleton(
            DependencyInjectorResolver,
            container=__self__
        )
    )
```

## Troubleshooting

### "No handler found" Errors

**Problem:** `HandlerNotFoundError` when sending a request.

**Solutions:**

1. **Verify handler is registered:**
   ```python
   # For SimpleResolver
   print(resolver._handlers.keys())

   # For DI Resolver
   print(resolver._handler_providers.keys())
   ```

2. **Check request type inheritance:**
   ```python
   # Request must inherit from Request[T]
   class MyRequest(Request[MyResponse]):  # ✓ Correct
       pass

   class MyRequest:  # ✗ Wrong - missing Request inheritance
       pass
   ```

3. **Verify provider is in container:**
   ```python
   # List all providers
   for name, provider in container.providers.items():
       print(f"{name}: {provider}")
   ```

### Handler Type Mismatch

**Problem:** `HandlerTypeMismatchError` when registering.

**Solution:** Ensure handler matches request type:

```python
class Handler1(Handler[Request1]):  # Handles Request1
    pass

# ✓ Correct
resolver.register(Request1, Handler1())

# ✗ Wrong - type mismatch
resolver.register(Request2, Handler1())
```

### Circular Dependencies

**Problem:** Handlers depend on each other circularly.

**Solution:** Use lazy injection or refactor:

```python
# Use providers.Callable for lazy injection
class Container(containers.DeclarativeContainer):
    handler_a = providers.Factory(
        HandlerA,
        handler_b=providers.Callable(lambda: container.handler_b())
    )

    handler_b = providers.Factory(
        HandlerB,
        handler_a=providers.Callable(lambda: container.handler_a())
    )
```

## See Also

- [Handlers Guide](handlers.md) - Understanding handlers
- [Dependency Injection](dependency-injection.md) - DI integration guide
- [API Reference: Resolvers](../api/resolvers.md) - Complete API documentation
- [API Reference: DI Resolver](../api/di-resolver.md) - DI resolver API
