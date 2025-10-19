# Mediator

The `Mediator` class is the central coordination point in PyMediate. It routes requests to their appropriate handlers using a resolver.

## Overview

The mediator provides a simple, type-safe interface for sending requests and receiving responses. It decouples request senders from request handlers, enabling clean separation of concerns.

The mediator doesn't know anything about specific requests or handlers - it's completely generic and relies on a resolver to provide handler instances.

## API Reference

::: pymediate.mediator.Mediator
    options:
      show_root_heading: true
      show_source: true
      members_order: source
      heading_level: 2

## Usage Examples

### Basic Usage with SimpleResolver

The most straightforward way to use the mediator:

```python
from pymediate import Mediator, SimpleResolver

# Set up resolver
resolver = SimpleResolver()
resolver.register(CreateUserRequest, CreateUserHandler())
resolver.register(GetUserRequest, GetUserHandler())

# Create mediator
mediator = Mediator(resolver)

# Send requests
user = mediator.send(CreateUserRequest(username="alice", email="alice@example.com"))
print(f"Created user {user.username} with ID {user.user_id}")

retrieved = mediator.send(GetUserRequest(user_id=user.user_id))
print(f"Retrieved user {retrieved.username}")
```

### Usage with Dependency Injection

Integration with dependency-injector:

```python
from dependency_injector import containers, providers
from pymediate import Mediator, DependencyInjectorResolver

class AppContainer(containers.DeclarativeContainer):
    # Services
    database = providers.Singleton(Database)
    email_service = providers.Singleton(EmailService)

    # Handlers
    create_user_handler = providers.Factory(
        CreateUserHandler,
        database=database,
        email_service=email_service
    )

    get_user_handler = providers.Factory(
        GetUserHandler,
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

# Use the mediator
container = AppContainer()
mediator = container.mediator()
response = mediator.send(CreateUserRequest(username="alice", email="alice@example.com"))
```

### In a FastAPI Application

Integrate the mediator with web frameworks:

```python
from fastapi import FastAPI, Depends
from pymediate import Mediator

app = FastAPI()

def get_mediator() -> Mediator:
    # Set up your mediator
    resolver = SimpleResolver()
    resolver.register(CreateUserRequest, CreateUserHandler())
    return Mediator(resolver)

@app.post("/users")
def create_user(
    username: str,
    email: str,
    mediator: Mediator = Depends(get_mediator)
):
    request = CreateUserRequest(username=username, email=email)
    response = mediator.send(request)
    return {"user_id": response.user_id, "username": response.username}
```

### With Multiple Requests

Handle different types of requests through a single mediator:

```python
mediator = Mediator(resolver)

# Create a user
create_response = mediator.send(
    CreateUserRequest(username="alice", email="alice@example.com")
)

# Update the user
update_response = mediator.send(
    UpdateUserRequest(user_id=create_response.user_id, email="newemail@example.com")
)

# Delete the user
delete_response = mediator.send(
    DeleteUserRequest(user_id=create_response.user_id)
)

# Each response is correctly typed!
```

## Key Concepts

### Type Safety

The mediator provides full type safety from request to response:

```python
# Type checker knows the return type!
response: UserCreatedResponse = mediator.send(CreateUserRequest(...))
#        ^^^^^^^^^^^^^^^^^^^
#        Inferred from Request[UserCreatedResponse]

print(response.user_id)     # Valid
print(response.username)    # Valid
print(response.invalid)     # Type error!
```

### Decoupling

The mediator decouples senders from handlers:

```python
# The web layer doesn't know about handlers
@app.post("/users")
def create_user(username: str, email: str, mediator: Mediator = Depends()):
    response = mediator.send(CreateUserRequest(username=username, email=email))
    return response

# The CLI doesn't know about handlers
def create_user_cli(username: str, email: str, mediator: Mediator):
    response = mediator.send(CreateUserRequest(username=username, email=email))
    print(f"Created user {response.username}")

# They both use the same business logic, but don't depend on it!
```

### Single Responsibility

The mediator has one job: route requests to handlers. It doesn't:

- Know about specific requests or handlers
- Perform validation
- Handle errors (beyond routing errors)
- Contain business logic

This keeps it simple, testable, and reusable.

## Error Handling

The mediator can raise errors during request routing:

```python
try:
    response = mediator.send(UnknownRequest())
except HandlerNotFoundError as e:
    print(f"No handler for {e.request_type.__name__}")
    print(f"Available handlers: {e.available_handlers}")
except DIContainerError as e:
    print(f"DI container failed: {e.reason}")
```

Business logic errors from handlers bubble up naturally:

```python
class CreateUserHandler(Handler[CreateUserRequest]):
    def __call__(self, request: CreateUserRequest) -> UserCreatedResponse:
        if not request.username:
            raise ValueError("Username required")  # This bubbles up
        ...

try:
    response = mediator.send(CreateUserRequest(username="", email="test@example.com"))
except ValueError as e:
    print(f"Validation error: {e}")
```

## Testing

The mediator is easy to test and mock:

```python
def test_user_creation():
    # Arrange
    resolver = SimpleResolver()
    resolver.register(CreateUserRequest, CreateUserHandler())
    mediator = Mediator(resolver)

    # Act
    response = mediator.send(
        CreateUserRequest(username="testuser", email="test@example.com")
    )

    # Assert
    assert response.user_id > 0
    assert response.username == "testuser"

def test_with_mock_mediator():
    # Mock the mediator for testing consumers
    mock_mediator = Mock(spec=Mediator)
    mock_mediator.send.return_value = UserCreatedResponse(
        user_id=1, username="testuser"
    )

    # Test code that uses the mediator
    result = some_function_that_uses_mediator(mock_mediator)

    # Verify mediator was called correctly
    mock_mediator.send.assert_called_once()
```

## Best Practices

### Use a Single Mediator Instance

Create one mediator instance and reuse it throughout your application:

```python
# Good - single instance
mediator = container.mediator()
app.state.mediator = mediator

# Bad - creating new instances
def handle_request():
    mediator = Mediator(SimpleResolver())  # Don't do this repeatedly!
```

### Inject the Mediator

Use dependency injection to provide the mediator:

```python
# Good - injected dependency
def create_user(mediator: Mediator, username: str, email: str):
    return mediator.send(CreateUserRequest(username=username, email=email))

# Bad - global mediator
GLOBAL_MEDIATOR = Mediator(...)  # Harder to test

def create_user(username: str, email: str):
    return GLOBAL_MEDIATOR.send(...)  # Tightly coupled
```

### Let Errors Bubble

Don't catch and suppress errors in the mediator:

```python
# Good - let errors bubble
response = mediator.send(request)

# Bad - hiding errors
try:
    response = mediator.send(request)
except Exception:
    return None  # Information lost!
```

## See Also

- [Request](request.md) - Define requests
- [Handler](handler.md) - Process requests
- [Resolvers](resolvers.md) - Resolve handler instances
- [User Guide: Mediator](../guide/mediator.md) - Detailed guide
