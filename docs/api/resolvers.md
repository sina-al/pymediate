# Resolvers

Resolvers are responsible for providing handler instances to the mediator. PyMediate provides two built-in resolvers and allows you to create custom ones.

## Overview

The `Resolver` protocol defines the interface for handler resolution. Any class implementing this protocol can be used with the Mediator, making PyMediate flexible and framework-agnostic.

The built-in `SimpleResolver` provides a straightforward dict-based implementation suitable for most applications.

## API Reference

### Resolver Protocol

::: pymediate.resolver.Resolver
    options:
      show_root_heading: true
      show_source: true
      members_order: source
      heading_level: 3

### SimpleResolver

::: pymediate.resolver.SimpleResolver
    options:
      show_root_heading: true
      show_source: true
      members_order: source
      heading_level: 3

## Usage Examples

### Basic Usage with SimpleResolver

The most common way to use resolvers:

```python
from pymediate import SimpleResolver, Mediator

# Create resolver
resolver = SimpleResolver()

# Register handlers
resolver.register(CreateUserRequest, CreateUserHandler())
resolver.register(UpdateUserRequest, UpdateUserHandler())
resolver.register(DeleteUserRequest, DeleteUserHandler())

# Use with mediator
mediator = Mediator(resolver)
response = mediator.send(CreateUserRequest(username="alice", email="alice@example.com"))
```

### Pre-populated Resolver

Initialize with handlers upfront:

```python
handlers = {
    CreateUserRequest: CreateUserHandler(database),
    UpdateUserRequest: UpdateUserHandler(database),
    DeleteUserRequest: DeleteUserHandler(database),
}

resolver = SimpleResolver(handlers)
mediator = Mediator(resolver)
```

### Resolver with Dependencies

Handlers can have their own dependencies:

```python
database = Database()
email_service = EmailService()

resolver = SimpleResolver()
resolver.register(
    CreateUserRequest,
    CreateUserHandler(database=database, email_service=email_service)
)

mediator = Mediator(resolver)
```

### Custom Resolver

Implement the Resolver protocol for custom resolution logic:

```python
from pymediate import Resolver

class CustomResolver:
    def __init__(self, handler_factory):
        self.handler_factory = handler_factory

    def resolve(self, request_class: type) -> Handler:
        # Custom logic to create/retrieve handlers
        return self.handler_factory.create(request_class)

# Use it
resolver = CustomResolver(my_factory)
mediator = Mediator(resolver)
```

### Lazy Initialization

Resolve handlers lazily:

```python
class LazyResolver:
    def __init__(self):
        self._handler_classes = {}
        self._handler_cache = {}

    def register_class(self, request_class: type, handler_class: type):
        self._handler_classes[request_class] = handler_class

    def resolve(self, request_class: type) -> Handler:
        if request_class not in self._handler_cache:
            handler_class = self._handler_classes[request_class]
            self._handler_cache[request_class] = handler_class()
        return self._handler_cache[request_class]
```

## Key Concepts

### Resolver Protocol

The `Resolver` protocol is simple - just implement a `resolve()` method:

```python
class MyResolver:
    def resolve(self, request_class: type) -> Handler:
        # Return a handler instance for the request type
        ...
```

### Type Safety

SimpleResolver validates handlers at registration time:

```python
resolver = SimpleResolver()

# This works
resolver.register(CreateUserRequest, CreateUserHandler())

# This raises HandlerTypeMismatchError
resolver.register(CreateUserRequest, UpdateUserHandler())  # Wrong handler!
```

### Handler Lifecycle

With `SimpleResolver`, handlers are singletons - the same instance is returned each time:

```python
resolver.register(CreateUserRequest, CreateUserHandler())

handler1 = resolver.resolve(CreateUserRequest)
handler2 = resolver.resolve(CreateUserRequest)

assert handler1 is handler2  # Same instance
```

For per-request handler instances, use `DependencyInjectorResolver` with Factory providers.

### Framework Agnostic

Resolvers work with any dependency injection framework or pattern:

- Dict-based (SimpleResolver)
- Function factories
- DI containers (DependencyInjectorResolver)
- Service locators
- Custom strategies

## Choosing a Resolver

### Use SimpleResolver When:

- Your application is relatively simple
- You don't need complex dependency graphs
- Singleton handlers are acceptable
- You want minimal setup

Example use cases:
- Small applications
- Prototypes
- Testing
- CLIs with simple workflows

### Use DependencyInjectorResolver When:

- You have complex dependency graphs
- You need per-request handler instances (Factory pattern)
- You're already using dependency-injector
- You want centralized DI configuration

Example use cases:
- Large applications
- Microservices
- Applications with many dependencies
- When you need lifecycle management

### Use Custom Resolver When:

- You have specific resolution requirements
- You're using a different DI framework
- You need special handler lifecycle management
- You want custom caching or pooling

## Best Practices

### Register All Handlers at Startup

Register handlers during application initialization:

```python
def setup_mediator() -> Mediator:
    resolver = SimpleResolver()

    # Register all handlers
    resolver.register(CreateUserRequest, CreateUserHandler(database))
    resolver.register(UpdateUserRequest, UpdateUserHandler(database))
    resolver.register(DeleteUserRequest, DeleteUserHandler(database))
    # ... more handlers ...

    return Mediator(resolver)

# At app startup
mediator = setup_mediator()
```

### Use Dependency Injection

Don't create dependencies inside the resolver registration:

```python
# Good - dependencies injected
database = Database()
resolver.register(CreateUserRequest, CreateUserHandler(database))

# Bad - creates new dependencies
resolver.register(CreateUserRequest, CreateUserHandler(Database()))
```

### Handle Missing Handlers Gracefully

The resolver will raise `HandlerNotFoundError` with helpful information:

```python
try:
    handler = resolver.resolve(UnknownRequest)
except HandlerNotFoundError as e:
    print(f"No handler for {e.request_type.__name__}")
    print(f"Available: {[h.__name__ for h in e.available_handlers]}")
```

## Testing

Resolvers are easy to test:

```python
def test_resolver_registration():
    resolver = SimpleResolver()
    handler = CreateUserHandler()

    resolver.register(CreateUserRequest, handler)

    resolved = resolver.resolve(CreateUserRequest)
    assert resolved is handler

def test_handler_type_mismatch():
    resolver = SimpleResolver()

    with pytest.raises(HandlerTypeMismatchError):
        resolver.register(CreateUserRequest, UpdateUserHandler())

def test_handler_not_found():
    resolver = SimpleResolver()

    with pytest.raises(HandlerNotFoundError):
        resolver.resolve(UnknownRequest)
```

## See Also

- [DI Integration](di-resolver.md) - DependencyInjectorResolver details
- [Mediator](mediator.md) - Using resolvers with the mediator
- [User Guide: Resolvers](../guide/resolvers.md) - Detailed guide
- [User Guide: Dependency Injection](../guide/dependency-injection.md) - DI patterns
