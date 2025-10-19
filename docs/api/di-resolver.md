# DI Integration

The `DependencyInjectorResolver` integrates PyMediate with the [dependency-injector](https://python-dependency-injector.ets-labs.org/) library, enabling automatic handler discovery and resolution from DI containers.

## Overview

This resolver uses type inspection to automatically discover handlers from a dependency-injector Container, **without requiring any naming conventions**. Handler providers can have any name - the resolver finds them by checking if they're Handler instances.

The resolver scans the container once at initialization and builds an O(1) lookup cache, making handler resolution extremely fast.

## API Reference

::: pymediate.di_resolver.DependencyInjectorResolver
    options:
      show_root_heading: true
      show_source: true
      members_order: source
      heading_level: 2

## Installation

Install PyMediate with DI support:

```bash
pip install pymediate[di]
# or
uv add 'pymediate[di]'
```

## Usage Examples

### Basic Setup

The most common pattern:

```python
from dependency_injector import containers, providers
from pymediate import Mediator, DependencyInjectorResolver

class AppContainer(containers.DeclarativeContainer):
    # Services
    database = providers.Singleton(Database, connection_string="...")
    email_service = providers.Singleton(EmailService, api_key="...")

    # Handlers - names don't matter!
    create_user_handler = providers.Factory(
        CreateUserHandler,
        database=database,
        email_service=email_service
    )

    update_user_handler = providers.Factory(
        UpdateUserHandler,
        database=database
    )

    # Mediator setup
    __self__ = providers.Self()
    resolver = providers.Singleton(
        DependencyInjectorResolver,
        container=__self__
    )
    mediator = providers.Singleton(
        Mediator,
        resolver=resolver
    )

# Use it
container = AppContainer()
mediator = container.mediator()

response = mediator.send(CreateUserRequest(username="alice", email="alice@example.com"))
```

### With Complex Dependencies

Handlers can have deep dependency trees:

```python
class AppContainer(containers.DeclarativeContainer):
    # Infrastructure
    config = providers.Singleton(Config)
    database = providers.Singleton(Database, config=config)
    cache = providers.Singleton(RedisCache, config=config)
    logger = providers.Singleton(Logger, config=config)

    # Services
    email_service = providers.Singleton(
        EmailService,
        smtp_host=config.provided.smtp_host,
        logger=logger
    )

    user_repository = providers.Singleton(
        UserRepository,
        database=database,
        cache=cache
    )

    # Handlers with injected dependencies
    create_user = providers.Factory(
        CreateUserHandler,
        repository=user_repository,
        email_service=email_service,
        logger=logger
    )

    get_user = providers.Factory(
        GetUserHandler,
        repository=user_repository,
        cache=cache
    )

    # Mediator
    __self__ = providers.Self()
    resolver = providers.Singleton(DependencyInjectorResolver, container=__self__)
    mediator = providers.Singleton(Mediator, resolver=resolver)
```

### Factory vs Singleton Providers

Choose the right provider type for your handlers:

```python
class AppContainer(containers.DeclarativeContainer):
    database = providers.Singleton(Database)

    # Factory - new handler instance per request
    create_user_handler = providers.Factory(
        CreateUserHandler,
        database=database
    )

    # Singleton - same handler instance every time
    get_user_handler = providers.Singleton(
        GetUserHandler,
        database=database
    )

    __self__ = providers.Self()
    resolver = providers.Singleton(DependencyInjectorResolver, container=__self__)
    mediator = providers.Singleton(Mediator, resolver=resolver)
```

When to use Factory:
- Handlers maintain per-request state
- You want fresh instances for each resolution
- Handlers are not thread-safe

When to use Singleton:
- Handlers are stateless
- Handlers are thread-safe
- Better performance (no instantiation overhead)

### With FastAPI

Integrate with FastAPI dependency injection:

```python
from fastapi import FastAPI, Depends
from dependency_injector import containers, providers
from dependency_injector.wiring import Provide, inject

class AppContainer(containers.DeclarativeContainer):
    # ... container setup ...
    pass

# Create container
container = AppContainer()

# Create FastAPI app
app = FastAPI()

# Wire container to app
container.wire(modules=[__name__])

@app.post("/users")
@inject
def create_user(
    username: str,
    email: str,
    mediator: Mediator = Depends(Provide[AppContainer.mediator])
):
    request = CreateUserRequest(username=username, email=email)
    response = mediator.send(request)
    return {"user_id": response.user_id, "username": response.username}
```

### Multiple Containers

You can have multiple containers for different contexts:

```python
class WebContainer(containers.DeclarativeContainer):
    # Web-specific handlers and services
    ...

class CLIContainer(containers.DeclarativeContainer):
    # CLI-specific handlers and services
    ...

# Use appropriate container for context
web_container = WebContainer()
web_mediator = web_container.mediator()

cli_container = CLIContainer()
cli_mediator = cli_container.mediator()
```

## Key Concepts

### Automatic Handler Discovery

The resolver finds handlers by type inspection, not naming:

```python
# All these provider names work - resolver finds handlers by type!
class AppContainer(containers.DeclarativeContainer):
    user_creator = providers.Factory(CreateUserHandler, ...)  # ✓
    handler1 = providers.Factory(CreateUserHandler, ...)       # ✓
    foo = providers.Factory(CreateUserHandler, ...)            # ✓
    create_user_handler = providers.Factory(CreateUserHandler, ...) # ✓
```

### Container Scanning

The container is scanned once at initialization:

1. Iterate through all providers
2. Call each provider to get an instance
3. Check if it's a Handler using isinstance()
4. Extract request type from Handler._request_type
5. Build request_type -> provider mapping

This happens in `__init__`, so there's no runtime scanning overhead.

### O(1) Resolution

After initialization, handler resolution is O(1):

```python
# First call - O(1) lookup from pre-built cache
handler = resolver.resolve(CreateUserRequest)

# Subsequent calls - O(1) lookup
handler = resolver.resolve(CreateUserRequest)
```

### Provider Lifecycle

The resolver calls providers, so lifecycle is controlled by the provider type:

```python
# Factory - new instance every time
providers.Factory(CreateUserHandler, ...)

# Singleton - same instance every time
providers.Singleton(CreateUserHandler, ...)
```

## Error Handling

### Handler Not Found

If no handler is registered for a request:

```python
try:
    handler = resolver.resolve(UnknownRequest)
except HandlerNotFoundError as e:
    print(f"No handler for {e.request_type.__name__}")
    print(f"Available: {[t.__name__ for t in e.available_handlers]}")
```

### DI Container Error

If the container fails to provide a handler:

```python
try:
    handler = resolver.resolve(CreateUserRequest)
except DIContainerError as e:
    print(f"Container error: {e.reason}")
    print(f"Request type: {e.request_type.__name__}")
```

Common causes:
- Missing dependencies in the handler
- Circular dependencies
- Configuration errors

## Best Practices

### Use Factory Providers for Handlers

Unless you have a good reason, use Factory providers:

```python
# Good - fresh handler per request
create_user_handler = providers.Factory(CreateUserHandler, database=database)

# OK - if handler is truly stateless
get_user_handler = providers.Singleton(GetUserHandler, database=database)
```

### One Container per Application

Create a single container and reuse it:

```python
# Good - single container
container = AppContainer()
mediator = container.mediator()

# Bad - multiple containers for same app
container1 = AppContainer()
container2 = AppContainer()  # Don't do this!
```

### Keep Handler Providers Together

Group handler providers for maintainability:

```python
class AppContainer(containers.DeclarativeContainer):
    # Infrastructure
    database = providers.Singleton(Database)

    # Services
    email_service = providers.Singleton(EmailService)

    # User handlers
    create_user = providers.Factory(CreateUserHandler, ...)
    update_user = providers.Factory(UpdateUserHandler, ...)
    delete_user = providers.Factory(DeleteUserHandler, ...)

    # Order handlers
    create_order = providers.Factory(CreateOrderHandler, ...)
    cancel_order = providers.Factory(CancelOrderHandler, ...)
```

### Don't Modify Container After Resolver Creation

The resolver scans once at initialization:

```python
container = AppContainer()
resolver = DependencyInjectorResolver(container)

# This won't be discovered - resolver already scanned!
container.new_handler = providers.Factory(NewHandler, ...)

# Instead, add handlers before creating resolver
container = AppContainer()
container.new_handler = providers.Factory(NewHandler, ...)
resolver = DependencyInjectorResolver(container)  # Now it's discovered
```

## Testing

### Testing with DI Container

```python
def test_mediator_with_di():
    container = AppContainer()
    mediator = container.mediator()

    response = mediator.send(CreateUserRequest(username="test", email="test@example.com"))

    assert response.user_id > 0
    assert response.username == "test"

def test_handler_dependencies():
    container = AppContainer()
    database = container.database()

    # Test that handlers get correct dependencies
    create_handler = container.create_user_handler()
    assert create_handler.database is database
```

### Testing with Override

Override providers for testing:

```python
def test_with_mock_database():
    container = AppContainer()

    # Override database with mock
    mock_db = Mock(spec=Database)
    container.database.override(mock_db)

    mediator = container.mediator()
    response = mediator.send(CreateUserRequest(username="test", email="test@example.com"))

    # Verify mock was called
    mock_db.insert_user.assert_called_once()
```

## See Also

- [Resolvers](resolvers.md) - SimpleResolver and custom resolvers
- [User Guide: Dependency Injection](../guide/dependency-injection.md) - Detailed DI guide
- [dependency-injector docs](https://python-dependency-injector.ets-labs.org/) - Full DI library documentation
