# Async/Await Support

PyMediate provides first-class support for asynchronous operations through the `pymediate.aio` package. This allows you to write handlers and mediators that work seamlessly with Python's `async`/`await` syntax.

## Quick Start

The async API mirrors the synchronous API, with handlers using `async def __call__` and mediators using `await send()`:

```python
import asyncio
from dataclasses import dataclass
from pymediate import Request, SimpleResolver
from pymediate.aio import Handler, Mediator

@dataclass
class UserResponse:
    user_id: int
    username: str

@dataclass
class CreateUserRequest(Request[UserResponse]):
    username: str
    email: str

class CreateUserHandler(Handler[CreateUserRequest]):
    async def __call__(self, request: CreateUserRequest) -> UserResponse:
        # Perform async database operation
        await asyncio.sleep(0.1)  # Simulated async I/O
        return UserResponse(user_id=1, username=request.username)

async def main():
    resolver = SimpleResolver()
    resolver.register(CreateUserHandler())
    mediator = Mediator(resolver)

    response = await mediator.send(CreateUserRequest(
        username="alice",
        email="alice@example.com"
    ))
    print(f"Created user {response.username} with ID {response.user_id}")

asyncio.run(main())
```

## Key Differences from Sync API

| Aspect | Sync API | Async API |
|--------|----------|-----------|
| Import | `from pymediate import Handler, Mediator` | `from pymediate.aio import Handler, Mediator` |
| Handler Method | `def __call__(self, request) -> Response` | `async def __call__(self, request) -> Response` |
| Mediator Send | `response = mediator.send(request)` | `response = await mediator.send(request)` |
| Request/Resolver | Same - `from pymediate import Request, SimpleResolver` | Same - `from pymediate import Request, SimpleResolver` |

## Async Database Operations

Here's a realistic example with async database access:

```python
import asyncio
from dataclasses import dataclass
from typing import Optional
from pymediate import Request, SimpleResolver
from pymediate.aio import Handler, Mediator

# Simulated async database
class AsyncDatabase:
    async def get_user(self, user_id: int) -> Optional[dict]:
        await asyncio.sleep(0.05)  # Simulate I/O
        return {"id": user_id, "name": "Alice", "email": "alice@example.com"}

    async def create_user(self, name: str, email: str) -> int:
        await asyncio.sleep(0.1)  # Simulate I/O
        return 42  # Generated user ID

# Request and Response types
@dataclass
class GetUserResponse:
    user_id: int
    name: str
    email: str

@dataclass
class GetUserRequest(Request[GetUserResponse]):
    user_id: int

@dataclass
class CreateUserResponse:
    user_id: int

@dataclass
class CreateUserRequest(Request[CreateUserResponse]):
    name: str
    email: str

# Handlers
class GetUserHandler(Handler[GetUserRequest]):
    def __init__(self, db: AsyncDatabase):
        self.db = db

    async def __call__(self, request: GetUserRequest) -> GetUserResponse:
        user = await self.db.get_user(request.user_id)
        if not user:
            raise ValueError(f"User {request.user_id} not found")
        return GetUserResponse(
            user_id=user["id"],
            name=user["name"],
            email=user["email"]
        )

class CreateUserHandler(Handler[CreateUserRequest]):
    def __init__(self, db: AsyncDatabase):
        self.db = db

    async def __call__(self, request: CreateUserRequest) -> CreateUserResponse:
        user_id = await self.db.create_user(request.name, request.email)
        return CreateUserResponse(user_id=user_id)

async def main():
    # Setup
    db = AsyncDatabase()
    resolver = SimpleResolver()
    resolver.register(GetUserHandler(db))
    resolver.register(CreateUserHandler(db))
    mediator = Mediator(resolver)

    # Create a user
    create_response = await mediator.send(CreateUserRequest(
        name="Bob",
        email="bob@example.com"
    ))
    print(f"Created user with ID: {create_response.user_id}")

    # Get the user
    get_response = await mediator.send(GetUserRequest(user_id=42))
    print(f"Retrieved user: {get_response.name} ({get_response.email})")

asyncio.run(main())
```

## Concurrent Request Processing

One of the key benefits of async is the ability to process multiple requests concurrently:

```python
import asyncio
from dataclasses import dataclass
from pymediate import Request, SimpleResolver
from pymediate.aio import Handler, Mediator

@dataclass
class ApiResponse:
    data: str
    duration: float

@dataclass
class FetchApiRequest(Request[ApiResponse]):
    endpoint: str
    delay: float  # Simulated API latency

class FetchApiHandler(Handler[FetchApiRequest]):
    async def __call__(self, request: FetchApiRequest) -> ApiResponse:
        start = asyncio.get_event_loop().time()
        await asyncio.sleep(request.delay)  # Simulate API call
        duration = asyncio.get_event_loop().time() - start
        return ApiResponse(
            data=f"Data from {request.endpoint}",
            duration=duration
        )

async def main():
    resolver = SimpleResolver()
    resolver.register(FetchApiHandler())
    mediator = Mediator(resolver)

    # Process multiple requests concurrently
    start = asyncio.get_event_loop().time()

    responses = await asyncio.gather(
        mediator.send(FetchApiRequest("/users", 0.5)),
        mediator.send(FetchApiRequest("/posts", 0.3)),
        mediator.send(FetchApiRequest("/comments", 0.4)),
    )

    total_duration = asyncio.get_event_loop().time() - start

    for response in responses:
        print(f"{response.data} (took {response.duration:.2f}s)")

    print(f"\nTotal time: {total_duration:.2f}s")
    # Should be ~0.5s (max of all delays), not 1.2s (sum of delays)

asyncio.run(main())
```

## Error Handling

Error handling works the same way in async handlers:

```python
import asyncio
from dataclasses import dataclass
from pymediate import Request, SimpleResolver
from pymediate.aio import Handler, Mediator

class ValidationError(Exception):
    pass

@dataclass
class ProcessResponse:
    result: int

@dataclass
class ProcessRequest(Request[ProcessResponse]):
    value: int

class ProcessHandler(Handler[ProcessRequest]):
    async def __call__(self, request: ProcessRequest) -> ProcessResponse:
        if request.value < 0:
            raise ValidationError("Value must be non-negative")

        await asyncio.sleep(0.1)
        return ProcessResponse(result=request.value * 2)

async def main():
    resolver = SimpleResolver()
    resolver.register(ProcessHandler())
    mediator = Mediator(resolver)

    try:
        response = await mediator.send(ProcessRequest(value=-1))
    except ValidationError as e:
        print(f"Validation failed: {e}")

    response = await mediator.send(ProcessRequest(value=21))
    print(f"Result: {response.result}")

asyncio.run(main())
```

## Mixing Sync and Async

You can have both sync and async handlers in the same application. Simply use the appropriate imports:

```python
from pymediate import Handler as SyncHandler
from pymediate.aio import Handler as AsyncHandler
from pymediate import Request, Mediator as SyncMediator
from pymediate.aio import Mediator as AsyncMediator

# Sync request/handler
class SyncResponse:
    value: int

class SyncRequest(Request[SyncResponse]):
    pass

class MySyncHandler(SyncHandler[SyncRequest]):
    def __call__(self, request: SyncRequest) -> SyncResponse:
        return SyncResponse(value=42)

# Async request/handler
class AsyncResponse:
    value: int

class AsyncRequest(Request[AsyncResponse]):
    pass

class MyAsyncHandler(AsyncHandler[AsyncRequest]):
    async def __call__(self, request: AsyncRequest) -> AsyncResponse:
        await asyncio.sleep(0.1)
        return AsyncResponse(value=42)
```

## Type Safety

The async API maintains full type safety. Mypy will catch type errors:

```python
from pymediate import Request
from pymediate.aio import Handler

class Response:
    value: int

class MyRequest(Request[Response]):
    pass

# ❌ This will fail - missing async keyword
class BadHandler(Handler[MyRequest]):
    def __call__(self, request: MyRequest) -> Response:  # Should be async!
        return Response(value=42)
# Raises: InvalidHandlerSignatureError: __call__ must be async

# ✅ This is correct
class GoodHandler(Handler[MyRequest]):
    async def __call__(self, request: MyRequest) -> Response:
        return Response(value=42)
```

## Best Practices

1. **Use async for I/O-bound operations**: Database queries, API calls, file I/O
2. **Use sync for CPU-bound operations**: Heavy computation, data processing
3. **Process requests concurrently**: Use `asyncio.gather()` for parallel requests
4. **Handle errors appropriately**: Use try/except in handlers and at the call site
5. **Keep handlers focused**: Each handler should do one thing well
6. **Test both sync and async paths**: Ensure handlers work correctly in isolation

## Performance Considerations

- **Async is not always faster**: For CPU-bound tasks, sync may be better
- **Concurrent != Parallel**: Async is concurrent but single-threaded
- **I/O benefits the most**: Async shines when waiting for external resources
- **Context switching overhead**: Very simple operations may be slower with async

## Integration with Async Frameworks

### FastAPI

```python
from fastapi import FastAPI, Depends
from pymediate import Request, SimpleResolver
from pymediate.aio import Handler, Mediator

app = FastAPI()

# Setup mediator (typically done at startup)
resolver = SimpleResolver()
mediator = Mediator(resolver)

# Dependency injection
def get_mediator() -> Mediator:
    return mediator

@app.post("/users/")
async def create_user(
    username: str,
    email: str,
    mediator: Mediator = Depends(get_mediator)
):
    response = await mediator.send(CreateUserRequest(
        username=username,
        email=email
    ))
    return {"user_id": response.user_id, "username": response.username}
```

### aiohttp

```python
from aiohttp import web
from pymediate.aio import Mediator

async def create_user(request):
    mediator = request.app["mediator"]
    data = await request.json()

    response = await mediator.send(CreateUserRequest(
        username=data["username"],
        email=data["email"]
    ))

    return web.json_response({
        "user_id": response.user_id,
        "username": response.username
    })

app = web.Application()
app["mediator"] = mediator
app.router.add_post("/users/", create_user)
```

## See Also

- [Handlers Guide](../guide/handlers.md)
- [Mediator Guide](../guide/mediator.md)
- [Type Safety](../advanced/type-safety.md)
- [FastAPI Example](fastapi.md)
