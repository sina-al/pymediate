# Quick Start

This guide will help you get started with PyMediate in 5 minutes.

## Your First Mediator

Let's build a simple user creation feature using PyMediate.

### Step 1: Define Your Response

First, define what your handler will return. We'll use a simple dataclass:

```python
from dataclasses import dataclass

@dataclass
class UserCreated:
    user_id: int
    username: str
    email: str
```

### Step 2: Define Your Request

Inherit from Request[ResponseType] to link the request to its response:

```python
from pymediate import Request

@dataclass
class CreateUser(Request[UserCreated]):
    username: str
    email: str
```

!!! tip "Why Request[T] inheritance?"
    Inheriting from Request[ResponseType] tells PyMediate what type of response this request expects.
    This enables automatic type inference and validation, and works perfectly with dataclasses!

### Step 3: Create a Handler

Handlers implement the business logic. PyMediate automatically knows which handler handles which request:

```python
from pymediate import Handler

class CreateUserHandler(Handler[CreateUser]):
    def __init__(self):
        self.next_id = 1
        self.users = {}

    def __call__(self, request: CreateUser) -> UserCreated:
        # Your business logic here
        user_id = self.next_id
        self.next_id += 1

        self.users[user_id] = {
            'username': request.username,
            'email': request.email
        }

        return UserCreated(
            user_id=user_id,
            username=request.username,
            email=request.email
        )
```

### Step 4: Set Up the Mediator

Create a mediator and register your handler:

```python
from pymediate import Mediator, SimpleResolver

# Create resolver and register handler
resolver = SimpleResolver()
resolver.register(CreateUserHandler())

# Create mediator
mediator = Mediator(resolver)
```

### Step 5: Use It!

Now you can send requests through the mediator:

```python
# Send a request
request = CreateUser(username="alice", email="alice@example.com")
response = mediator.send(request)

# Use the response
print(f"Created user {response.username} with ID {response.user_id}")
# Output: Created user alice with ID 1
```

## Complete Example

Here's the complete code in one file:

```python
from dataclasses import dataclass
from pymediate import Request, Handler, Mediator, SimpleResolver

# 1. Define response
@dataclass
class UserCreated:
    user_id: int
    username: str
    email: str

# 2. Define request
@dataclass
class CreateUser(Request[UserCreated]):
    username: str
    email: str

# 3. Create handler
class CreateUserHandler(Handler[CreateUser]):
    def __init__(self):
        self.next_id = 1
        self.users = {}

    def __call__(self, request: CreateUser) -> UserCreated:
        user_id = self.next_id
        self.next_id += 1

        self.users[user_id] = {
            'username': request.username,
            'email': request.email
        }

        return UserCreated(
            user_id=user_id,
            username=request.username,
            email=request.email
        )

# 4. Set up mediator
resolver = SimpleResolver()
resolver.register(CreateUserHandler())
mediator = Mediator(resolver)

# 5. Use it!
response = mediator.send(CreateUser(username="alice", email="alice@example.com"))
print(f"Created user {response.username} with ID {response.user_id}")
```

## Type Safety in Action

PyMediate validates types at class definition time:

```python
class WrongHandler(Handler[CreateUser]):
    def __call__(self, request: CreateUser) -> str:  # ❌ Wrong return type!
        return "oops"

# TypeError: WrongHandler.__call__ must return UserCreated, got str
```

## Async Support

PyMediate also supports async/await for asynchronous operations:

```python
from pymediate.aio import Handler, Mediator

class CreateUserHandler(Handler[CreateUser]):
    async def __call__(self, request: CreateUser) -> UserCreated:
        # Can use await for async operations
        await database.save_user(request.username, request.email)
        return UserCreated(
            user_id=1,
            username=request.username,
            email=request.email
        )

# Use async mediator
mediator = Mediator(resolver)
response = await mediator.send(CreateUser(username="alice", email="alice@example.com"))
```

See the [async examples](../examples/async.md) for more details.

## Next Steps

Now that you understand the basics:

- Learn about [core concepts](concepts.md)
- Try [async/await support](../examples/async.md)
- Explore [dependency injection](../guide/dependency-injection.md)
- See more [examples](../examples/basic.md)
- Read the [user guide](../guide/requests-responses.md)
