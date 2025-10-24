# Pipeline Behaviors

Pipeline behaviors are middleware components that wrap around request processing, enabling clean implementation of cross-cutting concerns without modifying your handler code.

## Table of Contents

- [What Are Pipeline Behaviors?](#what-are-pipeline-behaviors)
- [When to Use Pipeline Behaviors](#when-to-use-pipeline-behaviors)
- [Basic Behavior Structure](#basic-behavior-structure)
- [Creating Behaviors](#creating-behaviors)
- [Chaining Multiple Behaviors](#chaining-multiple-behaviors)
- [Async Behaviors](#async-behaviors)
- [Common Use Cases](#common-use-cases)
- [Behavior Patterns](#behavior-patterns)
- [Testing Behaviors](#testing-behaviors)
- [Best Practices](#best-practices)
- [Integration with Mediator](#integration-with-mediator)

## What Are Pipeline Behaviors?

Pipeline behaviors are inspired by **MediatR's IPipelineBehavior** pattern from the .NET ecosystem. They provide a way to implement middleware-like functionality that wraps around your request handlers.

### Key Characteristics

1. **Middleware Pattern**: Execute code before and after handler execution
2. **Type-Safe**: Full generic type support with compile-time checking
3. **Composable**: Chain multiple behaviors together
4. **Non-Invasive**: Add functionality without modifying handlers
5. **Reusable**: Write once, use across many request types

### The Pipeline Chain

```
Request → Behavior 1 → Behavior 2 → Behavior 3 → Handler → Response
             ↓            ↓            ↓            ↓
          Before       Before       Before       Execute
             ↓            ↓            ↓            ↓
          After ←      After ←      After ←     Return
```

Each behavior can execute logic both before and after the next step in the chain.

## When to Use Pipeline Behaviors

Use pipeline behaviors for **cross-cutting concerns** - functionality that applies to multiple handlers:

### Perfect Use Cases

- ✅ **Logging and Auditing**: Track all requests passing through the system
- ✅ **Performance Monitoring**: Measure execution time for all handlers
- ✅ **Validation**: Apply common validation rules
- ✅ **Caching**: Cache responses based on request data
- ✅ **Transaction Management**: Wrap handler execution in database transactions
- ✅ **Error Handling**: Centralized error logging and recovery
- ✅ **Authentication/Authorization**: Check permissions before handler execution
- ✅ **Rate Limiting**: Throttle requests based on rules
- ✅ **Retry Logic**: Automatically retry failed operations

### When NOT to Use Behaviors

- ❌ **Handler-Specific Logic**: Use the handler itself
- ❌ **Business Rules**: Keep in handlers where they belong
- ❌ **Request Transformation**: Use separate request types instead
- ❌ **Complex Conditionals**: Behaviors should be simple and focused

## Basic Behavior Structure

A pipeline behavior is any class that implements the `PipelineBehavior` protocol:

```python
from collections.abc import Callable
from pymediate.pipeline import PipelineBehavior

class MyBehavior:
    def __call__(
        self,
        request: RequestT,
        next: Callable[[], ResponseT],
    ) -> ResponseT:
        # Code before handler (pre-processing)
        print(f"Before: {type(request).__name__}")

        # Call the next step in the pipeline
        response = next()

        # Code after handler (post-processing)
        print(f"After: {type(response).__name__}")

        return response
```

### The `next` Parameter

The `next` parameter is a callable that represents the next step in the pipeline:
- It could be another behavior
- It could be the final handler
- It returns the response when called

**You must call `next()` to continue the pipeline!** If you don't, the handler never executes.

## Creating Behaviors

### Logging Behavior

Track all requests passing through your system:

```python
from datetime import datetime

class LoggingBehavior:
    """Logs all requests with timestamps."""

    def __init__(self, logger):
        self.logger = logger

    def __call__(self, request, next):
        request_name = type(request).__name__
        start_time = datetime.now()

        self.logger.info(f"[{start_time}] Processing: {request_name}")

        try:
            response = next()
            duration = (datetime.now() - start_time).total_seconds()
            self.logger.info(
                f"[{datetime.now()}] Completed: {request_name} "
                f"in {duration:.3f}s"
            )
            return response
        except Exception as e:
            self.logger.error(
                f"[{datetime.now()}] Failed: {request_name} - {e}"
            )
            raise
```

### Performance Monitoring Behavior

Measure execution time for all handlers:

```python
import time
from collections.abc import Callable

class TimingBehavior:
    """Measures and reports execution time."""

    def __init__(self, metrics_collector):
        self.metrics = metrics_collector

    def __call__(self, request, next):
        start = time.perf_counter()

        try:
            response = next()
            duration = time.perf_counter() - start

            # Report metrics
            self.metrics.record_timing(
                handler=type(request).__name__,
                duration=duration,
                success=True
            )

            return response
        except Exception as e:
            duration = time.perf_counter() - start
            self.metrics.record_timing(
                handler=type(request).__name__,
                duration=duration,
                success=False
            )
            raise
```

### Validation Behavior

Apply common validation rules:

```python
class ValidationBehavior:
    """Validates requests before processing."""

    def __call__(self, request, next):
        # Check if request has a validate method
        if hasattr(request, 'validate'):
            validation_errors = request.validate()
            if validation_errors:
                raise ValueError(f"Validation failed: {validation_errors}")

        return next()
```

### Caching Behavior

Cache responses to avoid redundant work:

```python
import hashlib
import json

class CachingBehavior:
    """Caches responses based on request data."""

    def __init__(self, cache_store, ttl=300):
        self.cache = cache_store
        self.ttl = ttl

    def __call__(self, request, next):
        # Generate cache key from request
        cache_key = self._generate_key(request)

        # Check cache
        cached_response = self.cache.get(cache_key)
        if cached_response is not None:
            return cached_response

        # Execute handler
        response = next()

        # Cache the response
        self.cache.set(cache_key, response, ttl=self.ttl)

        return response

    def _generate_key(self, request):
        """Generate a cache key from request data."""
        request_type = type(request).__name__
        request_data = json.dumps(request.__dict__, sort_keys=True)
        return hashlib.sha256(
            f"{request_type}:{request_data}".encode()
        ).hexdigest()
```

### Transaction Behavior

Wrap handler execution in a database transaction:

```python
class TransactionBehavior:
    """Wraps handler execution in a database transaction."""

    def __init__(self, session_factory):
        self.session_factory = session_factory

    def __call__(self, request, next):
        session = self.session_factory()

        try:
            # Begin transaction
            session.begin()

            # Execute handler
            response = next()

            # Commit if successful
            session.commit()
            return response
        except Exception:
            # Rollback on error
            session.rollback()
            raise
        finally:
            session.close()
```

### Retry Behavior

Automatically retry failed operations:

```python
import time

class RetryBehavior:
    """Retries failed operations with exponential backoff."""

    def __init__(self, max_attempts=3, base_delay=0.1):
        self.max_attempts = max_attempts
        self.base_delay = base_delay

    def __call__(self, request, next):
        last_exception = None

        for attempt in range(self.max_attempts):
            try:
                return next()
            except Exception as e:
                last_exception = e

                if attempt < self.max_attempts - 1:
                    # Calculate delay with exponential backoff
                    delay = self.base_delay * (2 ** attempt)
                    time.sleep(delay)
                else:
                    # Last attempt failed, raise the exception
                    raise

        # Should never reach here, but makes type checker happy
        raise last_exception
```

## Chaining Multiple Behaviors

Behaviors execute in the order they're provided to the `Pipeline`:

```python
from pymediate.pipeline import Pipeline
from pymediate import Handler, Request

# Create behaviors
logging = LoggingBehavior(logger)
timing = TimingBehavior(metrics)
validation = ValidationBehavior()
caching = CachingBehavior(cache)

# Create handler
class GetUserHandler(Handler[GetUserRequest]):
    def __call__(self, request: GetUserRequest) -> GetUserResponse:
        return GetUserResponse(...)

# Compose pipeline
handler = GetUserHandler(database)
pipeline = Pipeline(
    behaviors=[
        logging,      # Executes first (outermost)
        timing,       # Then timing
        validation,   # Then validation
        caching,      # Then caching (innermost before handler)
    ],
    handler=handler
)

# Execution flow:
# logging.before → timing.before → validation.before → caching.before
#   → check cache → [cache miss] → handler → cache.after
#   → validation.after → timing.after → logging.after
```

### Execution Order Visualization

```python
behaviors = [A, B, C]
handler = MyHandler()
pipeline = Pipeline(behaviors, handler)

# When you call pipeline(request), this happens:
A.before()
  B.before()
    C.before()
      handler(request)  # ← The actual handler executes here
    C.after()
  B.after()
A.after()
```

### Practical Example

```python
from pymediate.pipeline import Pipeline

# Setup
database = Database()
cache = RedisCache()
logger = Logger()
metrics = MetricsCollector()

# Create handler
handler = GetUserHandler(database)

# Compose pipeline with multiple concerns
pipeline = Pipeline(
    behaviors=[
        LoggingBehavior(logger),           # Log everything
        TimingBehavior(metrics),            # Measure performance
        ValidationBehavior(),               # Validate request
        CachingBehavior(cache, ttl=600),   # Cache for 10 minutes
    ],
    handler=handler
)

# Use it
request = GetUserRequest(user_id=123)
response = pipeline(request)

# Output:
# [2025-01-15 10:30:00] Processing: GetUserRequest
# [Cache] Checking cache for key: abc123...
# [Cache] Cache miss, executing handler
# [Database] Executing query: SELECT * FROM users WHERE id = 123
# [Cache] Storing result in cache with TTL 600s
# [Metrics] GetUserRequest completed in 0.042s
# [2025-01-15 10:30:00] Completed: GetUserRequest in 0.042s
```

## Async Behaviors

For async handlers, use `pymediate.aio.pipeline`:

```python
import asyncio
from pymediate.aio.pipeline import Pipeline, PipelineBehavior

class AsyncLoggingBehavior:
    """Async logging behavior."""

    def __init__(self, logger):
        self.logger = logger

    async def __call__(self, request, next):
        # Async logging
        await self.logger.log_async(f"Processing: {type(request).__name__}")

        response = await next()

        await self.logger.log_async(f"Completed: {type(request).__name__}")

        return response
```

### Async Transaction Behavior

```python
class AsyncTransactionBehavior:
    """Async transaction management."""

    def __init__(self, async_session):
        self.session = async_session

    async def __call__(self, request, next):
        async with self.session.begin():
            response = await next()
            # Transaction commits automatically if no exception
            return response
        # Transaction rolls back automatically on exception
```

### Async Caching Behavior

```python
class AsyncCachingBehavior:
    """Async caching with Redis."""

    def __init__(self, redis_client):
        self.redis = redis_client

    async def __call__(self, request, next):
        cache_key = self._generate_key(request)

        # Check cache asynchronously
        cached = await self.redis.get(cache_key)
        if cached:
            return self._deserialize(cached)

        # Execute handler
        response = await next()

        # Cache asynchronously
        await self.redis.setex(
            cache_key,
            300,  # 5 minutes TTL
            self._serialize(response)
        )

        return response
```

### Using Async Pipelines

```python
from pymediate.aio import Handler, Mediator
from pymediate.aio.pipeline import Pipeline

# Create async handler
class AsyncGetUserHandler(Handler[GetUserRequest]):
    async def __call__(self, request: GetUserRequest) -> GetUserResponse:
        user = await database.get_user_async(request.user_id)
        return GetUserResponse(user_id=user.id, username=user.username)

# Setup async pipeline
handler = AsyncGetUserHandler(async_database)
pipeline = Pipeline(
    behaviors=[
        AsyncLoggingBehavior(logger),
        AsyncCachingBehavior(redis),
    ],
    handler=handler
)

# Use with async/await
response = await pipeline(GetUserRequest(user_id=123))
```

## Common Use Cases

### 1. Request/Response Logging with Audit Trail

```python
class AuditBehavior:
    """Logs requests and responses for audit compliance."""

    def __init__(self, audit_log):
        self.audit_log = audit_log

    def __call__(self, request, next):
        # Log request
        request_id = self._generate_id()
        self.audit_log.log_request(
            request_id=request_id,
            request_type=type(request).__name__,
            request_data=self._serialize(request),
            timestamp=datetime.now()
        )

        try:
            response = next()

            # Log successful response
            self.audit_log.log_response(
                request_id=request_id,
                success=True,
                response_data=self._serialize(response)
            )

            return response
        except Exception as e:
            # Log error
            self.audit_log.log_response(
                request_id=request_id,
                success=False,
                error=str(e)
            )
            raise
```

### 2. Authentication and Authorization

```python
class AuthorizationBehavior:
    """Checks if user has permission to execute request."""

    def __init__(self, permission_service):
        self.permissions = permission_service

    def __call__(self, request, next):
        # Check if request has required_permission attribute
        if hasattr(request, 'required_permission'):
            user_id = request.user_id  # Assume all requests have user_id
            permission = request.required_permission

            if not self.permissions.has_permission(user_id, permission):
                raise PermissionError(
                    f"User {user_id} lacks permission: {permission}"
                )

        return next()
```

### 3. Rate Limiting

```python
class RateLimitBehavior:
    """Limits request rate per user."""

    def __init__(self, redis_client, max_requests=100, window=60):
        self.redis = redis_client
        self.max_requests = max_requests
        self.window = window  # seconds

    def __call__(self, request, next):
        user_id = getattr(request, 'user_id', 'anonymous')
        key = f"rate_limit:{user_id}"

        # Get current count
        current = int(self.redis.get(key) or 0)

        if current >= self.max_requests:
            raise TooManyRequestsError(
                f"Rate limit exceeded: {current}/{self.max_requests}"
            )

        # Increment counter
        pipe = self.redis.pipeline()
        pipe.incr(key)
        pipe.expire(key, self.window)
        pipe.execute()

        return next()
```

### 4. Dead Letter Queue for Failed Requests

```python
class DeadLetterBehavior:
    """Sends failed requests to a dead letter queue."""

    def __init__(self, queue):
        self.dead_letter_queue = queue

    def __call__(self, request, next):
        try:
            return next()
        except Exception as e:
            # Log to dead letter queue for later inspection
            self.dead_letter_queue.enqueue({
                'request_type': type(request).__name__,
                'request_data': self._serialize(request),
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })
            raise
```

### 5. Response Transformation

```python
class ResponseEnrichmentBehavior:
    """Adds metadata to all responses."""

    def __call__(self, request, next):
        response = next()

        # Add metadata
        if hasattr(response, 'metadata'):
            response.metadata['processed_at'] = datetime.now()
            response.metadata['request_type'] = type(request).__name__
            response.metadata['version'] = '1.0'

        return response
```

## Behavior Patterns

### Conditional Execution

```python
class ConditionalBehavior:
    """Only executes inner logic for certain request types."""

    def __init__(self, predicate, inner_behavior):
        self.predicate = predicate
        self.inner_behavior = inner_behavior

    def __call__(self, request, next):
        if self.predicate(request):
            # Delegate to inner behavior
            return self.inner_behavior(request, next)
        else:
            # Skip inner behavior
            return next()

# Usage
logging_for_commands = ConditionalBehavior(
    predicate=lambda req: isinstance(req, CommandRequest),
    inner_behavior=LoggingBehavior(logger)
)
```

### Circuit Breaker Pattern

```python
class CircuitBreakerBehavior:
    """Implements circuit breaker pattern."""

    def __init__(self, failure_threshold=5, timeout=60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failures = 0
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN

    def __call__(self, request, next):
        if self.state == 'OPEN':
            # Check if timeout has passed
            if (datetime.now() - self.last_failure_time).seconds > self.timeout:
                self.state = 'HALF_OPEN'
            else:
                raise CircuitBreakerOpenError("Circuit breaker is OPEN")

        try:
            response = next()

            # Success - reset if half-open
            if self.state == 'HALF_OPEN':
                self.state = 'CLOSED'
                self.failures = 0

            return response
        except Exception as e:
            self.failures += 1
            self.last_failure_time = datetime.now()

            if self.failures >= self.failure_threshold:
                self.state = 'OPEN'

            raise
```

### Decorator Pattern

```python
class BehaviorDecorator:
    """Wraps another behavior with additional functionality."""

    def __init__(self, inner_behavior, logger):
        self.inner = inner_behavior
        self.logger = logger

    def __call__(self, request, next):
        self.logger.info(f"Before {type(self.inner).__name__}")
        response = self.inner(request, next)
        self.logger.info(f"After {type(self.inner).__name__}")
        return response
```

## Testing Behaviors

### Unit Testing a Behavior

```python
def test_logging_behavior():
    # Mock logger
    logger = MockLogger()
    behavior = LoggingBehavior(logger)

    # Mock request and response
    request = SampleRequest(value=10)
    expected_response = SampleResponse(value=20)

    # Mock next callable
    def mock_next():
        return expected_response

    # Execute behavior
    response = behavior(request, mock_next)

    # Verify
    assert response == expected_response
    assert logger.info_called_with("Processing: SampleRequest")
    assert logger.info_called_with("Completed: SampleRequest")


def test_validation_behavior_rejects_invalid():
    behavior = ValidationBehavior()

    # Invalid request
    request = SampleRequest(value=-1)
    request.validate = lambda: ["Value must be positive"]

    def mock_next():
        raise AssertionError("Should not reach handler")

    # Should raise validation error
    with pytest.raises(ValueError, match="Validation failed"):
        behavior(request, mock_next)


def test_caching_behavior_caches_response():
    cache = {}
    behavior = CachingBehavior(cache_store=cache)

    request = SampleRequest(value=5)
    response = SampleResponse(value=10)

    call_count = 0
    def mock_next():
        nonlocal call_count
        call_count += 1
        return response

    # First call - should execute handler
    result1 = behavior(request, mock_next)
    assert call_count == 1
    assert result1 == response

    # Second call - should use cache
    result2 = behavior(request, mock_next)
    assert call_count == 1  # Handler not called again
    assert result2 == response
```

### Integration Testing with Pipeline

```python
def test_pipeline_with_multiple_behaviors():
    # Setup
    logger = MockLogger()
    metrics = MockMetrics()
    cache = {}

    handler = SampleHandler()
    pipeline = Pipeline(
        behaviors=[
            LoggingBehavior(logger),
            TimingBehavior(metrics),
            CachingBehavior(cache),
        ],
        handler=handler
    )

    # Execute
    request = SampleRequest(value=5)
    response = pipeline(request)

    # Verify all behaviors executed
    assert response.value == 10
    assert logger.logged("Processing: SampleRequest")
    assert metrics.has_timing_for("SampleRequest")
    assert len(cache) > 0


@pytest.mark.asyncio
async def test_async_pipeline_with_behaviors():
    logger = MockAsyncLogger()
    handler = AsyncSampleHandler()

    pipeline = Pipeline(
        behaviors=[AsyncLoggingBehavior(logger)],
        handler=handler
    )

    request = SampleRequest(value=5)
    response = await pipeline(request)

    assert response.value == 10
    assert await logger.has_log("Processing: SampleRequest")
```

## Best Practices

### 1. Keep Behaviors Focused

Each behavior should have a single responsibility:

```python
# ✅ GOOD: Focused behavior
class LoggingBehavior:
    def __call__(self, request, next):
        logger.info(f"Processing: {type(request).__name__}")
        response = next()
        logger.info(f"Completed: {type(request).__name__}")
        return response

# ❌ BAD: Too many responsibilities
class MegaBehavior:
    def __call__(self, request, next):
        logger.info("Processing")  # Logging
        if not valid(request):  # Validation
            raise ValueError()
        cache_check()  # Caching
        response = next()
        send_metrics()  # Metrics
        return response
```

### 2. Make Behaviors Reusable

Design behaviors to work with any request type:

```python
# ✅ GOOD: Works with any request
class TimingBehavior:
    def __call__(self, request, next):
        start = time.time()
        response = next()
        duration = time.time() - start
        metrics.record(duration)
        return response

# ❌ BAD: Tied to specific request type
class TimingBehavior:
    def __call__(self, request: GetUserRequest, next):
        # Only works with GetUserRequest
        ...
```

### 3. Always Call `next()`

Unless you intentionally want to short-circuit:

```python
# ✅ GOOD: Always calls next
class ValidationBehavior:
    def __call__(self, request, next):
        if not is_valid(request):
            raise ValueError("Invalid request")
        return next()  # ← Always call next

# ⚠️ CAUTION: Only short-circuit intentionally
class CacheShortCircuitBehavior:
    def __call__(self, request, next):
        cached = cache.get(key)
        if cached:
            return cached  # ← Intentional short-circuit
        return next()
```

### 4. Handle Exceptions Appropriately

```python
# ✅ GOOD: Log and re-raise
class ErrorLoggingBehavior:
    def __call__(self, request, next):
        try:
            return next()
        except Exception as e:
            logger.error(f"Request failed: {e}")
            raise  # Re-raise so caller knows about error

# ❌ BAD: Swallow exceptions
class BadBehavior:
    def __call__(self, request, next):
        try:
            return next()
        except Exception:
            return None  # Caller doesn't know something went wrong!
```

### 5. Inject Dependencies

```python
# ✅ GOOD: Dependencies injected
class LoggingBehavior:
    def __init__(self, logger):
        self.logger = logger

# ❌ BAD: Creating dependencies
class LoggingBehavior:
    def __init__(self):
        self.logger = Logger()  # Hard to test
```

### 6. Order Matters

Think carefully about behavior order:

```python
# ✅ GOOD: Logical order
Pipeline([
    AuthenticationBehavior(),  # Check auth first
    AuthorizationBehavior(),   # Then permissions
    ValidationBehavior(),      # Then validate
    CachingBehavior(),         # Then check cache
    LoggingBehavior(),         # Log everything
], handler)

# ❌ BAD: Illogical order
Pipeline([
    CachingBehavior(),         # Cache before auth check!
    LoggingBehavior(),         # Log before validation!
    ValidationBehavior(),
    AuthorizationBehavior(),
], handler)
```

### 7. Document Behavior Contracts

```python
class CachingBehavior:
    """Caches responses based on request data.

    Requirements:
        - Request must be hashable or have __dict__
        - Response must be serializable
        - Cache store must implement get(key) and set(key, value, ttl)

    Behavior:
        - Generates cache key from request type and data
        - Returns cached response if available
        - Caches response after handler execution
        - TTL defaults to 300 seconds (5 minutes)
    """
```

## Integration with Mediator

Pipeline behaviors can be used directly with handlers or integrated into the mediator's service configuration:

### Option 1: Wrap Individual Handlers

```python
from pymediate import Services, Mediator
from pymediate.pipeline import Pipeline

# Create handler with pipeline
handler = GetUserHandler(database)
pipeline = Pipeline([LoggingBehavior(logger)], handler)

# Register pipeline instead of handler
services = Services()
services.add(GetUserRequest, pipeline)

mediator = Mediator(services.provider())
response = mediator.send(GetUserRequest(user_id=123))
```

### Option 2: Create Reusable Pipeline Factory

```python
def create_pipeline(handler, behaviors=None):
    """Factory for creating pipelines with standard behaviors."""
    default_behaviors = [
        LoggingBehavior(logger),
        TimingBehavior(metrics),
        ValidationBehavior(),
    ]

    all_behaviors = default_behaviors + (behaviors or [])
    return Pipeline(all_behaviors, handler)

# Use factory
services.add(GetUserRequest, create_pipeline(GetUserHandler(db)))
services.add(CreateUserRequest, create_pipeline(CreateUserHandler(db)))
```

### Option 3: Apply Behaviors to Multiple Handlers

```python
# Standard behaviors for all handlers
standard_behaviors = [
    LoggingBehavior(logger),
    TimingBehavior(metrics),
]

# Specific behaviors for commands
command_behaviors = standard_behaviors + [
    TransactionBehavior(session),
    ValidationBehavior(),
]

# Register handlers with appropriate pipelines
services.add(GetUserRequest,
    Pipeline(standard_behaviors, GetUserHandler(db)))

services.add(CreateUserRequest,
    Pipeline(command_behaviors, CreateUserHandler(db)))
```

---

## Next Steps

- [Handlers Guide](handlers.md) - Learn about handlers
- [API Reference](../api/pipeline.md) - Detailed pipeline API documentation
- [Examples](../examples/pipeline-behaviors.md) - More pipeline behavior examples
- [Best Practices](../advanced/best-practices.md) - Advanced patterns
