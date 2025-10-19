# Handler

The `Handler` class is the base class for all handlers in PyMediate. Handlers contain your business logic and are responsible for processing requests and returning responses.

## Overview

Handlers inherit from `Handler[RequestT]` where `RequestT` is the type of request they process. The response type is automatically inferred from the request's `Request[ResponseT]` declaration.

PyMediate validates handler signatures at class definition time, ensuring type safety before your code even runs.

## API Reference

::: pymediate.handler.Handler
    options:
      show_root_heading: true
      show_source: true
      members_order: source
      heading_level: 2

## Usage Examples

### Basic Handler

The simplest handler processes a request and returns a response:

```python
from dataclasses import dataclass
from pymediate import Request, Handler

@dataclass
class UserCreatedResponse:
    user_id: int
    username: str

@dataclass
class CreateUserRequest(Request[UserCreatedResponse]):
    username: str
    email: str

class CreateUserHandler(Handler[CreateUserRequest]):
    def __call__(self, request: CreateUserRequest) -> UserCreatedResponse:
        # Business logic here
        user_id = 1  # Simulated ID generation
        return UserCreatedResponse(user_id=user_id, username=request.username)
```

### Handler with Dependencies

Handlers can accept dependencies via their constructor:

```python
class CreateUserHandler(Handler[CreateUserRequest]):
    def __init__(self, database: Database, email_service: EmailService):
        self.database = database
        self.email_service = email_service

    def __call__(self, request: CreateUserRequest) -> UserCreatedResponse:
        # Insert user into database
        user_id = self.database.insert_user(
            username=request.username,
            email=request.email
        )

        # Send welcome email
        self.email_service.send_welcome(request.email)

        return UserCreatedResponse(user_id=user_id, username=request.username)
```

### Stateful Handler

Handlers can maintain state if needed:

```python
class UserCreationHandler(Handler[CreateUserRequest]):
    def __init__(self, database: Database):
        self.database = database
        self.users_created = 0

    def __call__(self, request: CreateUserRequest) -> UserCreatedResponse:
        user_id = self.database.insert_user(
            username=request.username,
            email=request.email
        )
        self.users_created += 1
        return UserCreatedResponse(user_id=user_id, username=request.username)
```

### Async Handler

Handlers can be async (note: requires async mediator support):

```python
class CreateUserHandler(Handler[CreateUserRequest]):
    def __init__(self, database: AsyncDatabase):
        self.database = database

    async def __call__(self, request: CreateUserRequest) -> UserCreatedResponse:
        user_id = await self.database.insert_user(
            username=request.username,
            email=request.email
        )
        return UserCreatedResponse(user_id=user_id, username=request.username)
```

## Key Concepts

### Automatic Response Type Inference

You only need to specify the request type - the response type is inferred:

```python
# Request declares response type
class CreateUserRequest(Request[UserCreatedResponse]):
    ...

# Handler inherits it automatically
class CreateUserHandler(Handler[CreateUserRequest]):
    def __call__(self, request: CreateUserRequest) -> UserCreatedResponse:
        #                                            ^^^^^^^^^^^^^^^^^^^
        #                                    Response type is inferred!
        ...
```

### Compile-Time Validation

Handler signatures are validated when the class is defined, not at runtime:

```python
# This will raise InvalidHandlerSignatureError at import time
class BadHandler(Handler[CreateUserRequest]):
    def __call__(self, request: CreateUserRequest) -> WrongResponse:  # Error!
        ...
```

### Handler Independence

Handlers are completely independent from each other and from the infrastructure:

- No coupling between handlers
- No framework dependencies
- Easy to test in isolation
- Can be deployed separately (e.g., as microservices)

### Registration

Handlers are automatically registered in the global handler registry when they're defined. The `Handler.get_handler_for_request()` class method can retrieve them:

```python
handler_class = Handler.get_handler_for_request(CreateUserRequest)
assert handler_class == CreateUserHandler
```

## Best Practices

### Single Responsibility

Each handler should handle exactly one type of request:

```python
# Good - focused handler
class CreateUserHandler(Handler[CreateUserRequest]):
    def __call__(self, request: CreateUserRequest) -> UserCreatedResponse:
        # Only creates users
        ...

# Bad - handler doing too much
class UserHandler(Handler[UserRequest]):
    def __call__(self, request: UserRequest) -> UserResponse:
        if request.action == "create":
            # Create logic
        elif request.action == "update":
            # Update logic
        # This should be separate handlers!
```

### Dependency Injection

Inject dependencies rather than creating them:

```python
# Good - dependencies injected
class CreateUserHandler(Handler[CreateUserRequest]):
    def __init__(self, database: Database):
        self.database = database

# Bad - creates its own dependencies
class CreateUserHandler(Handler[CreateUserRequest]):
    def __init__(self):
        self.database = Database()  # Hard to test!
```

### Error Handling

Let exceptions bubble up to be handled by the mediator or caller:

```python
class CreateUserHandler(Handler[CreateUserRequest]):
    def __call__(self, request: CreateUserRequest) -> UserCreatedResponse:
        # Validate
        if not request.username:
            raise ValueError("Username is required")

        # Let database errors bubble up
        user_id = self.database.insert_user(...)

        return UserCreatedResponse(user_id=user_id, username=request.username)
```

## See Also

- [Request](request.md) - Define requests
- [Mediator](mediator.md) - Route requests to handlers
- [Resolvers](resolvers.md) - Resolve handler instances
- [User Guide: Handlers](../guide/handlers.md) - Detailed guide
