# Quick start

This guide gets you started with PyMediate in 5 minutes: define a request and response, write a handler, wire it up, and send it through a mediator.

## The complete picture

Here's a full, runnable user-creation feature in one file:

```python
from dataclasses import dataclass
from pymediate import Request, Handler, Mediator, Services

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
services = Services()
services.add(CreateUserHandler())
provider = services.provider()
mediator = Mediator(provider)

# 5. Use it
response = mediator.send(CreateUser(username="alice", email="alice@example.com"))
print(f"Created user {response.username} with ID {response.user_id}")
# Output: Created user alice with ID 1
```

The rest of this page walks through each of those five numbered pieces.

## Your first mediator

### Step 1: Define your response

First, define what your handler returns. Use a simple dataclass:

```python
from dataclasses import dataclass

@dataclass
class UserCreated:
    user_id: int
    username: str
    email: str
```

### Step 2: Define your request

Inherit from `Request[ResponseType]` to link the request to its response:

```python
from pymediate import Request

@dataclass
class CreateUser(Request[UserCreated]):
    username: str
    email: str
```

!!! tip "Why Request[T] inheritance?"
    Inheriting from `Request[ResponseType]` tells PyMediate what type of response this request expects.
    This enables automatic type inference and validation, and works cleanly with dataclasses.

### Step 3: Create a handler

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

### Step 4: Set up the mediator

Create a service collection, build a provider, and create a mediator:

```python
from pymediate import Mediator, Services

# Collect your services
services = Services()
services.add(CreateUserHandler())

# Build a read-only service provider
provider = services.provider()

# Construct your mediator
mediator = Mediator(provider)
```

### Step 5: Use it

Now you can send requests through the mediator:

```python
# Send a request
request = CreateUser(username="alice", email="alice@example.com")
response = mediator.send(request)

# Use the response
print(f"Created user {response.username} with ID {response.user_id}")
# Output: Created user alice with ID 1
```

## Type safety in action

PyMediate validates types at class-definition time:

```python
class WrongHandler(Handler[CreateUser]):
    def __call__(self, request: CreateUser) -> str:  # ❌ Wrong return type
        return "oops"

# TypeError: WrongHandler.__call__ must return UserCreated, got str
```

## Async support

PyMediate also supports async/await for asynchronous operations:

```python
from pymediate import Services
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

# Set up async mediator
services = Services()
services.add(CreateUserHandler())

mediator = Mediator(services.provider())

response = await mediator.send(CreateUser(username="alice", email="alice@example.com"))
```

See the [async examples](../examples/async.md) for more details.

## Next steps

Now that you understand the basics:

- Learn about [core concepts](concepts.md).
- Try [async/await support](../examples/async.md).
- Explore [dependency injection](../guide/dependency-injection.md).
- See more [examples](../examples/basic.md).
- Read the [user guide](../guide/requests-responses.md).
