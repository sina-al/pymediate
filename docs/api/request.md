# Request

The `Request` class is the base class for all requests in PyMediate. It uses Python's generic type parameters to specify the expected response type, enabling automatic type inference and validation.

## Overview

All requests in PyMediate inherit from `Request[ResponseT]` where `ResponseT` is the type of response the handler will return. This creates a type-safe contract between requests and their handlers.

The response type is automatically registered when you define a Request subclass, making it available for runtime validation and type checking throughout the mediator pattern.

## API Reference

::: pymediate.request.Request
    options:
      show_root_heading: true
      show_source: true
      members_order: source
      heading_level: 2

## Usage Examples

### Basic Request with Dataclasses

The most common pattern is to use dataclasses for both requests and responses:

```python
from dataclasses import dataclass
from pymediate import Request

@dataclass
class UserCreatedResponse:
    user_id: int
    username: str
    created_at: str

@dataclass
class CreateUserRequest(Request[UserCreatedResponse]):
    username: str
    email: str
    password: str
```

### Request with Regular Classes

You can also use regular Python classes:

```python
class UserCreatedResponse:
    def __init__(self, user_id: int, username: str):
        self.user_id = user_id
        self.username = username

class CreateUserRequest(Request[UserCreatedResponse]):
    def __init__(self, username: str, email: str):
        self.username = username
        self.email = email
```

### Query vs Command Pattern

Requests can represent either queries (read operations) or commands (write operations):

```python
# Query - returns data without side effects
@dataclass
class GetUserResponse:
    user_id: int
    username: str
    email: str

@dataclass
class GetUserQuery(Request[GetUserResponse]):
    user_id: int

# Command - performs an action with side effects
@dataclass
class UserDeletedResponse:
    success: bool
    user_id: int

@dataclass
class DeleteUserCommand(Request[UserDeletedResponse]):
    user_id: int
```

## Key Concepts

### Type Parameter Registration

When you define a Request subclass, the response type is automatically extracted and registered via the `__init_subclass__` hook. This happens at import time, not runtime, so there's no performance penalty.

### Framework Independence

Requests are completely independent of any delivery mechanism (HTTP, CLI, message queue, etc.). This allows you to:

- Reuse the same request across different interfaces
- Test business logic without framework dependencies
- Switch frameworks without changing core logic

### Type Safety

The response type parameter enables full type safety:

```python
# Type checker knows response is UserCreatedResponse
response = mediator.send(CreateUserRequest(username="alice", email="alice@example.com"))
print(response.user_id)  # Valid - type checker knows this field exists
print(response.invalid)  # Error - type checker catches this
```

## See Also

- [Handler](handler.md) - Process requests and return responses
- [Mediator](mediator.md) - Route requests to handlers
- [User Guide: Requests & Responses](../guide/requests-responses.md) - Detailed guide
