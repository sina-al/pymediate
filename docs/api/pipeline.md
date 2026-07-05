# Pipeline API reference

API documentation for pipeline behaviors and the Pipeline class.

## Overview

The pipeline module provides middleware-like functionality for wrapping request processing with cross-cutting concerns.

- **Module**: `pymediate.pipeline` (sync) / `pymediate.aio.pipeline` (async)
- **ABC**: `PipelineBehavior[RequestT: Request]`
- **Class**: `Pipeline[RequestT, ResponseT]`

## Selective behaviors

Behaviors can selectively apply to specific request types or mixins using the type parameter:

- `PipelineBehavior[Request]` - Universal (applies to all requests)
- `PipelineBehavior[CreateUserRequest]` - Specific request type
- `PipelineBehavior[AuthMixin]` - Requests with mixin

## Synchronous pipeline

### PipelineBehavior

::: pymediate.pipeline.PipelineBehavior
    options:
      show_root_heading: true
      show_source: true
      heading_level: 3

### Pipeline

::: pymediate.pipeline.Pipeline
    options:
      show_root_heading: true
      show_source: true
      heading_level: 3
      members:
        - __init__
        - __call__

## Asynchronous pipeline

### PipelineBehavior (Async)

::: pymediate.aio.pipeline.PipelineBehavior
    options:
      show_root_heading: true
      show_source: true
      heading_level: 3

### Pipeline (Async)

::: pymediate.aio.pipeline.Pipeline
    options:
      show_root_heading: true
      show_source: true
      heading_level: 3
      members:
        - __init__
        - __call__

## Usage examples

### Creating a simple behavior

```python
from pymediate.pipeline import PipelineBehavior

class LoggingBehavior:
    """A simple logging behavior."""

    def __init__(self, logger):
        self.logger = logger

    def __call__(self, request, next):
        self.logger.info(f"Processing: {type(request).__name__}")
        response = next()
        self.logger.info(f"Completed: {type(request).__name__}")
        return response
```

### Creating a pipeline

```python
from pymediate import Handler, Request
from pymediate.pipeline import Pipeline

class GetUserHandler(Handler[GetUserRequest]):
    def __call__(self, request: GetUserRequest) -> GetUserResponse:
        return GetUserResponse(...)

# Compose pipeline
handler = GetUserHandler(database)
pipeline = Pipeline(
    behaviors=[
        LoggingBehavior(logger),
        TimingBehavior(metrics),
        ValidationBehavior(),
    ],
    handler=handler
)

# Use pipeline
response = pipeline(GetUserRequest(user_id=123))
```

### Async pipeline

```python
from pymediate.aio import Handler
from pymediate.aio.pipeline import Pipeline

class AsyncGetUserHandler(Handler[GetUserRequest]):
    async def __call__(self, request: GetUserRequest) -> GetUserResponse:
        user = await database.get_user_async(request.user_id)
        return GetUserResponse(user_id=user.id, username=user.username)

# Compose async pipeline
handler = AsyncGetUserHandler(async_database)
pipeline = Pipeline(
    behaviors=[
        AsyncLoggingBehavior(logger),
        AsyncCachingBehavior(redis),
    ],
    handler=handler
)

# Use async pipeline
response = await pipeline(GetUserRequest(user_id=123))
```

## Type safety

The pipeline system is fully type-safe with generic type parameters.

```python
from pymediate.pipeline import Pipeline, PipelineBehavior
from typing import Callable

# Behavior with explicit types
class TypedBehavior:
    def __call__(
        self,
        request: GetUserRequest,
        next: Callable[[], GetUserResponse],
    ) -> GetUserResponse:
        response = next()
        return response

# Pipeline with type annotations
pipeline: Pipeline[GetUserRequest, GetUserResponse] = Pipeline(
    behaviors=[TypedBehavior()],
    handler=GetUserHandler()
)

# Type-safe usage
request: GetUserRequest = GetUserRequest(user_id=123)
response: GetUserResponse = pipeline(request)
```

## See also

- [Pipeline behaviors guide](../guide/pipeline-behaviors.md) - Comprehensive guide to pipeline behaviors.
- [Handler API reference](handler.md) - The `Handler` protocol.
- [Examples](../examples/pipeline-behaviors.md) - More pipeline examples.
