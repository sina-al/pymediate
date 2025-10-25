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

**Pipeline Behaviors are middleware** that automatically wrap around request processing. They enable cross-cutting concerns like logging, validation, caching, and error handling without modifying your handlers.

### Why Pipeline Behaviors?

Without behaviors, you'd need to add logging, validation, timing, etc. to **every handler**. This leads to:
- Duplicated code across handlers
- Difficult to maintain consistency
- Hard to add new cross-cutting concerns

Behaviors solve this by **automatically applying** to all requests:

```python
from pymediate import PipelineBehavior

class LoggingBehavior(PipelineBehavior):
    def __call__(self, request, next):
        print(f"Processing: {type(request).__name__}")
        response = next()
        print(f"Completed: {type(request).__name__}")
        return response

# Register behavior once - it applies to ALL requests
services = Services()
services.add(LoggingBehavior())  # Auto-discovered by mediator!
services.add(CreateUserHandler())
services.add(GetUserHandler())
# ... add more handlers

mediator = Mediator(services.provider())
```

### How Behaviors Work

Behaviors form a chain where each behavior wraps the next:

```
Request → Logging → Validation → Timing → Handler → Response
                                             ↓
        Logging ← Validation ← Timing ← Handler
```

**Execution flow:**
1. Request enters the first behavior (Logging)
2. Logging executes pre-processing, calls `next()`
3. Next behavior (Validation) executes, calls `next()`
4. Continue until Handler executes
5. Handler returns response
6. Each behavior's post-processing executes in reverse order

**Each behavior can:**
- Execute logic **before** the handler (pre-processing)
- Execute logic **after** the handler (post-processing)
- Modify the request or response
- Short-circuit the pipeline (skip handler)
- Handle/wrap errors

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

# 3. Optional: Add pipeline behaviors (automatically applied)
class LoggingBehavior(PipelineBehavior):
    def __call__(self, request, next):
        print(f"Before: {type(request).__name__}")
        response = next()
        print(f"After: {type(request).__name__}")
        return response

# 4. Setup mediator with behaviors and handlers
services = Services()
services.add(LoggingBehavior())      # Applied to ALL requests automatically
services.add(CreateUserHandler())
mediator = Mediator(services.provider())

# 5. Send requests - behaviors automatically wrap the handler
response = mediator.send(CreateUserRequest(username="alice"))
# Output: Before: CreateUserRequest
#         After: CreateUserRequest
```

---

## Next Steps

- [Quick Start](quick-start.md) - Get started with PyMediate
- [Handlers Guide](../guide/handlers.md) - Learn about handlers in detail
- [Pipeline Behaviors](../guide/pipeline-behaviors.md) - Add middleware to your requests
- [Examples](../examples/basic.md) - See real-world examples
