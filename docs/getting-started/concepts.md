# Core concepts

Learn the fundamental concepts behind PyMediate's mediator pattern implementation.

## Requests

**Requests.** Requests represent intentions — things you want your application to do. They're simple data containers that describe what action to perform.

```python
from pymediate import Request
from dataclasses import dataclass

@dataclass
class CreateUserRequest(Request[UserCreatedResponse]):
    username: str
    email: str
```

## Responses

**Responses.** Responses contain the results of processing a request — the data produced by the handler.

```python
@dataclass
class UserCreatedResponse:
    user_id: int
    username: str
    created_at: datetime
```

## Handlers

**Handlers.** Handlers contain your business logic. Each handler processes exactly one type of request and returns a response.

```python
from pymediate import Handler

class CreateUserHandler(Handler[CreateUserRequest]):
    def __call__(self, request: CreateUserRequest) -> UserCreatedResponse:
        # Your business logic here
        return UserCreatedResponse(...)
```

## Mediator

**Mediator.** The mediator coordinates request processing — it receives requests and delegates them to the appropriate handler.

```python
response = mediator.send(CreateUserRequest(username="alice", email="alice@example.com"))
```

## Pipeline behaviors

**Pipeline behaviors.** Pipeline behaviors are middleware that automatically wrap around request processing. They enable cross-cutting concerns like logging, validation, caching, and error handling without modifying your handlers.

### Why pipeline behaviors?

Without behaviors, you'd need to add logging, validation, and timing to every handler individually. That leads to:

- Duplicated code across handlers.
- Inconsistent behavior between handlers.
- Difficulty adding new cross-cutting concerns later.

Behaviors solve this by applying automatically to requests. They can be **universal** (apply to all requests) or **selective** (apply only to specific request types or mixins):

```python
from pymediate import Request, PipelineBehavior

# Universal behavior - applies to all requests
class LoggingBehavior(PipelineBehavior[Request]):
    def __call__(self, request, next):
        print(f"Processing: {type(request).__name__}")
        response = next()
        print(f"Completed: {type(request).__name__}")
        return response

# Register behavior once - it applies to all requests
services = Services()
services.add(LoggingBehavior())  # Auto-discovered by the mediator
services.add(CreateUserHandler())
services.add(GetUserHandler())
# ... add more handlers

mediator = Mediator(services.provider())
```

### How behaviors work

Behaviors form a chain where each behavior wraps the next:

```
Request → Logging → Validation → Timing → Handler → Response
                                             ↓
        Logging ← Validation ← Timing ← Handler
```

**Execution flow:**

1. The request enters the first behavior (Logging).
2. Logging executes its pre-processing, then calls `next()`.
3. The next behavior (Validation) executes, then calls `next()`.
4. This continues until the handler executes.
5. The handler returns a response.
6. Each behavior's post-processing executes in reverse order.

Each behavior can:

- Execute logic before the handler (pre-processing).
- Execute logic after the handler (post-processing).
- Modify the request or response.
- Short-circuit the pipeline by skipping the handler.
- Handle or wrap errors.

## Service provider

**Service provider.** Service providers resolve handler instances — they manage dependencies and provide handlers to the mediator when needed.

```python
from pymediate import Services, Mediator

services = Services()
services.add(CreateUserHandler(database))
provider = services.provider()
mediator = Mediator(provider)
```

---

## How they work together

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

# 3. Optional: add pipeline behaviors (applied automatically)
class LoggingBehavior(PipelineBehavior[Request]):
    def __call__(self, request, next):
        print(f"Before: {type(request).__name__}")
        response = next()
        print(f"After: {type(request).__name__}")
        return response

# 4. Set up the mediator with behaviors and handlers
services = Services()
services.add(LoggingBehavior())      # Applied to all requests automatically
services.add(CreateUserHandler())
mediator = Mediator(services.provider())

# 5. Send requests - behaviors automatically wrap the handler
response = mediator.send(CreateUserRequest(username="alice"))
# Output: Before: CreateUserRequest
#         After: CreateUserRequest
```

---

## Next steps

- [Quick start](quick-start.md) - Get started with PyMediate.
- [Handlers guide](../guide/handlers.md) - Learn about handlers in detail.
- [Pipeline behaviors](../guide/pipeline-behaviors.md) - Add middleware to your requests.
- [Examples](../examples/basic.md) - See real-world examples.
