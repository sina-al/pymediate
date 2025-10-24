# Core Concepts

Learn the fundamental concepts of PyMediate's mediator pattern implementation.

## Requests

**Requests represent intentions** - things you want your application to do. They're simple data containers that describe what action should be performed.

```python
from pymediate import Request
from dataclasses import dataclass

@dataclass
class CreateUserRequest(Request[UserCreatedResponse]):
    username: str
    email: str
```

## Responses

**Responses contain the results** of processing a request. They hold the data produced by the handler.

```python
@dataclass
class UserCreatedResponse:
    user_id: int
    username: str
    created_at: datetime
```

## Handlers

**Handlers contain your business logic**. Each handler processes exactly one type of request and returns a response.

```python
from pymediate import Handler

class CreateUserHandler(Handler[CreateUserRequest]):
    def __call__(self, request: CreateUserRequest) -> UserCreatedResponse:
        # Your business logic here
        return UserCreatedResponse(...)
```

## Mediator

**The Mediator coordinates** request processing. It receives requests and delegates them to the appropriate handler.

```python
response = mediator.send(CreateUserRequest(username="alice", email="alice@example.com"))
```

## Pipeline Behaviors

**Pipeline Behaviors are middleware** that wrap around request processing. They enable cross-cutting concerns like logging, validation, caching, and error handling without modifying your handlers.

```python
from pymediate.pipeline import Pipeline

class LoggingBehavior:
    def __call__(self, request, next):
        print(f"Processing: {type(request).__name__}")
        response = next()
        print(f"Completed: {type(request).__name__}")
        return response
```

Behaviors form a chain where each behavior wraps the next:

```
Request → Behavior 1 → Behavior 2 → Behavior 3 → Handler → Response
```

Each behavior can:
- Execute logic **before** the handler (pre-processing)
- Execute logic **after** the handler (post-processing)
- Modify the request or response
- Short-circuit the pipeline
- Handle errors

## Service Provider

**Service Providers resolve handler instances**. They manage dependencies and provide handlers to the mediator when needed.

```python
from pymediate import Services, Mediator

services = Services()
services.add(CreateUserHandler(database))
provider = services.provider()
mediator = Mediator(provider)
```

---

## How They Work Together

```python
# 1. Define your request and response
@dataclass
class CreateUserRequest(Request[UserCreatedResponse]):
    username: str

@dataclass
class UserCreatedResponse:
    user_id: int

# 2. Create a handler
class CreateUserHandler(Handler[CreateUserRequest]):
    def __call__(self, request: CreateUserRequest) -> UserCreatedResponse:
        return UserCreatedResponse(user_id=1)

# 3. Optional: Add pipeline behaviors
logging = LoggingBehavior()
timing = TimingBehavior()
pipeline = Pipeline([logging, timing], CreateUserHandler())

# 4. Setup mediator
services = Services()
services.add(CreateUserRequest, pipeline)  # or just the handler
mediator = Mediator(services.provider())

# 5. Send requests
response = mediator.send(CreateUserRequest(username="alice"))
```

---

## Next Steps

- [Quick Start](quick-start.md) - Get started with PyMediate
- [Handlers Guide](../guide/handlers.md) - Learn about handlers in detail
- [Pipeline Behaviors](../guide/pipeline-behaviors.md) - Add middleware to your requests
- [Examples](../examples/basic.md) - See real-world examples
