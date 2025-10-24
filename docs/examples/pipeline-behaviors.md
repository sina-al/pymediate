# Pipeline Behaviors Examples

Real-world examples of using pipeline behaviors to implement cross-cutting concerns.

## Basic Logging Example

```python
from dataclasses import dataclass
from datetime import datetime
from pymediate import Handler, Request, Mediator, Services
from pymediate.pipeline import Pipeline

# Define request and response
@dataclass
class CreateUserResponse:
    user_id: int
    username: str
    created_at: datetime

@dataclass
class CreateUserRequest(Request[CreateUserResponse]):
    username: str
    email: str

# Create handler
class CreateUserHandler(Handler[CreateUserRequest]):
    def __init__(self, database):
        self.database = database

    def __call__(self, request: CreateUserRequest) -> CreateUserResponse:
        user_id = self.database.create_user(
            username=request.username,
            email=request.email
        )
        return CreateUserResponse(
            user_id=user_id,
            username=request.username,
            created_at=datetime.now()
        )

# Create logging behavior
class LoggingBehavior:
    def __init__(self, logger):
        self.logger = logger

    def __call__(self, request, next):
        self.logger.info(f"[{datetime.now()}] Processing: {type(request).__name__}")
        try:
            response = next()
            self.logger.info(f"[{datetime.now()}] Success: {type(request).__name__}")
            return response
        except Exception as e:
            self.logger.error(f"[{datetime.now()}] Error: {type(request).__name__} - {e}")
            raise

# Setup
database = Database()
logger = Logger()

handler = CreateUserHandler(database)
pipeline = Pipeline([LoggingBehavior(logger)], handler)

# Register with mediator
services = Services()
services.add(CreateUserRequest, pipeline)
mediator = Mediator(services.provider())

# Use it
response = mediator.send(CreateUserRequest(username="alice", email="alice@example.com"))

# Output:
# [2025-01-15 10:30:00] Processing: CreateUserRequest
# [2025-01-15 10:30:00] Success: CreateUserRequest
```

## Performance Monitoring

```python
import time
from collections.abc import Callable

class PerformanceMonitoringBehavior:
    """Monitors performance and tracks slow requests."""

    def __init__(self, metrics_collector, slow_threshold=1.0):
        self.metrics = metrics_collector
        self.slow_threshold = slow_threshold

    def __call__(self, request, next):
        start = time.perf_counter()
        request_type = type(request).__name__

        try:
            response = next()
            duration = time.perf_counter() - start

            # Record metrics
            self.metrics.record_request(
                request_type=request_type,
                duration=duration,
                status="success"
            )

            # Alert on slow requests
            if duration > self.slow_threshold:
                self.metrics.alert_slow_request(
                    request_type=request_type,
                    duration=duration,
                    threshold=self.slow_threshold
                )

            return response
        except Exception as e:
            duration = time.perf_counter() - start
            self.metrics.record_request(
                request_type=request_type,
                duration=duration,
                status="error",
                error_type=type(e).__name__
            )
            raise

# Usage
metrics = MetricsCollector()
performance_behavior = PerformanceMonitoringBehavior(
    metrics_collector=metrics,
    slow_threshold=0.5  # Alert if request takes > 500ms
)

pipeline = Pipeline([performance_behavior], handler)
```

## Caching with Redis

```python
import hashlib
import json
import pickle

class RedisCachingBehavior:
    """Caches responses in Redis."""

    def __init__(self, redis_client, ttl=300, key_prefix="cache"):
        self.redis = redis_client
        self.ttl = ttl
        self.key_prefix = key_prefix

    def __call__(self, request, next):
        # Generate cache key
        cache_key = self._generate_cache_key(request)

        # Try to get from cache
        cached_data = self.redis.get(cache_key)
        if cached_data:
            print(f"[Cache HIT] {cache_key}")
            return pickle.loads(cached_data)

        print(f"[Cache MISS] {cache_key}")

        # Execute handler
        response = next()

        # Store in cache
        self.redis.setex(
            cache_key,
            self.ttl,
            pickle.dumps(response)
        )

        return response

    def _generate_cache_key(self, request):
        """Generate a unique cache key from request."""
        request_type = type(request).__name__
        request_data = json.dumps(
            {k: str(v) for k, v in request.__dict__.items()},
            sort_keys=True
        )
        hash_value = hashlib.sha256(request_data.encode()).hexdigest()[:16]
        return f"{self.key_prefix}:{request_type}:{hash_value}"

# Usage
import redis

redis_client = redis.Redis(host='localhost', port=6379, decode_responses=False)

pipeline = Pipeline(
    behaviors=[
        RedisCachingBehavior(redis_client, ttl=600),  # 10 minute cache
    ],
    handler=GetUserHandler(database)
)

# First call - cache miss, executes handler
response1 = pipeline(GetUserRequest(user_id=123))

# Second call - cache hit, returns cached response
response2 = pipeline(GetUserRequest(user_id=123))
```

## Database Transactions

```python
from sqlalchemy.orm import Session

class TransactionBehavior:
    """Wraps handler execution in a database transaction."""

    def __init__(self, session: Session):
        self.session = session

    def __call__(self, request, next):
        try:
            # Begin transaction
            self.session.begin()

            # Execute handler
            response = next()

            # Commit on success
            self.session.commit()
            return response

        except Exception as e:
            # Rollback on error
            self.session.rollback()
            print(f"[Transaction] Rolled back due to: {e}")
            raise

        finally:
            self.session.close()

# Usage with SQLAlchemy
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

engine = create_engine('postgresql://localhost/mydb')
SessionFactory = sessionmaker(bind=engine)

# Create transaction behavior
session = SessionFactory()
transaction_behavior = TransactionBehavior(session)

# Use in pipeline
pipeline = Pipeline(
    behaviors=[transaction_behavior],
    handler=CreateUserHandler(database)
)

# Handler execution is wrapped in transaction
response = pipeline(CreateUserRequest(username="alice", email="alice@example.com"))
```

## Request Validation

```python
from typing import Any

class ValidationBehavior:
    """Validates requests before processing."""

    def __call__(self, request, next):
        errors = []

        # Check if request has validate method
        if hasattr(request, 'validate'):
            validation_result = request.validate()
            if validation_result:
                errors.extend(validation_result)

        # Generic validation rules
        errors.extend(self._validate_fields(request))

        if errors:
            raise ValueError(f"Validation failed: {', '.join(errors)}")

        return next()

    def _validate_fields(self, request) -> list[str]:
        """Apply generic validation rules."""
        errors = []

        for field_name, field_value in request.__dict__.items():
            # Check for None values in required fields
            if field_value is None:
                errors.append(f"{field_name} is required")

            # Check string length
            if isinstance(field_value, str):
                if len(field_value) == 0:
                    errors.append(f"{field_name} cannot be empty")
                if len(field_value) > 255:
                    errors.append(f"{field_name} is too long (max 255 characters)")

        return errors

# Request with custom validation
@dataclass
class CreateProductRequest(Request[CreateProductResponse]):
    name: str
    price: float
    category: str

    def validate(self) -> list[str]:
        """Custom validation logic."""
        errors = []

        if self.price < 0:
            errors.append("Price must be non-negative")

        if self.price > 1000000:
            errors.append("Price exceeds maximum allowed value")

        if self.category not in ['electronics', 'books', 'clothing']:
            errors.append(f"Invalid category: {self.category}")

        return errors

# Usage
pipeline = Pipeline(
    behaviors=[ValidationBehavior()],
    handler=CreateProductHandler(database)
)

# Valid request - works
response = pipeline(CreateProductRequest(
    name="Laptop",
    price=999.99,
    category="electronics"
))

# Invalid request - raises ValidationError
try:
    response = pipeline(CreateProductRequest(
        name="",  # Empty name
        price=-100,  # Negative price
        category="invalid"  # Invalid category
    ))
except ValueError as e:
    print(f"Validation failed: {e}")
```

## Retry with Exponential Backoff

```python
import time
import random

class RetryBehavior:
    """Retries failed operations with exponential backoff."""

    def __init__(
        self,
        max_attempts=3,
        base_delay=0.1,
        max_delay=10.0,
        jitter=True
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.jitter = jitter

    def __call__(self, request, next):
        last_exception = None

        for attempt in range(1, self.max_attempts + 1):
            try:
                return next()

            except (ConnectionError, TimeoutError) as e:
                last_exception = e

                if attempt == self.max_attempts:
                    print(f"[Retry] All {self.max_attempts} attempts failed")
                    raise

                # Calculate delay with exponential backoff
                delay = min(self.base_delay * (2 ** (attempt - 1)), self.max_delay)

                # Add jitter to prevent thundering herd
                if self.jitter:
                    delay = delay * (0.5 + random.random())

                print(f"[Retry] Attempt {attempt} failed, retrying in {delay:.2f}s...")
                time.sleep(delay)

        # Should never reach here
        raise last_exception

# Usage
pipeline = Pipeline(
    behaviors=[
        RetryBehavior(max_attempts=3, base_delay=0.5),
        LoggingBehavior(logger),
    ],
    handler=CallExternalAPIHandler(api_client)
)

# Automatically retries on connection errors
response = pipeline(FetchDataRequest(url="https://api.example.com/data"))
```

## Authentication and Authorization

```python
class AuthenticationBehavior:
    """Verifies user is authenticated."""

    def __init__(self, token_service):
        self.token_service = token_service

    def __call__(self, request, next):
        # Check if request has auth_token
        if not hasattr(request, 'auth_token'):
            raise AuthenticationError("No authentication token provided")

        # Verify token
        user = self.token_service.verify_token(request.auth_token)
        if not user:
            raise AuthenticationError("Invalid or expired token")

        # Attach user to request for downstream use
        request.current_user = user

        return next()


class AuthorizationBehavior:
    """Checks user permissions."""

    def __init__(self, permission_service):
        self.permissions = permission_service

    def __call__(self, request, next):
        # Skip if no permissions required
        if not hasattr(request, 'required_permission'):
            return next()

        # Check if user was set by AuthenticationBehavior
        if not hasattr(request, 'current_user'):
            raise AuthorizationError("User not authenticated")

        # Check permissions
        user = request.current_user
        required = request.required_permission

        if not self.permissions.user_has_permission(user.id, required):
            raise AuthorizationError(
                f"User {user.id} lacks permission: {required}"
            )

        return next()

# Request with authentication
@dataclass
class DeleteUserRequest(Request[DeleteUserResponse]):
    user_id: int
    auth_token: str
    current_user: Any = None  # Set by AuthenticationBehavior

    # Define required permission
    required_permission = "users.delete"

# Usage
token_service = TokenService()
permission_service = PermissionService()

pipeline = Pipeline(
    behaviors=[
        AuthenticationBehavior(token_service),
        AuthorizationBehavior(permission_service),
        LoggingBehavior(logger),
    ],
    handler=DeleteUserHandler(database)
)

# Must provide valid token and have permission
response = pipeline(DeleteUserRequest(
    user_id=123,
    auth_token="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
))
```

## Async Pipeline with Multiple Behaviors

```python
import asyncio
from pymediate.aio.pipeline import Pipeline
from pymediate.aio import Handler

class AsyncLoggingBehavior:
    async def __call__(self, request, next):
        print(f"[START] {type(request).__name__}")
        response = await next()
        print(f"[END] {type(request).__name__}")
        return response


class AsyncCachingBehavior:
    def __init__(self, redis_client):
        self.redis = redis_client

    async def __call__(self, request, next):
        cache_key = f"{type(request).__name__}:{hash(request)}"

        # Check cache
        cached = await self.redis.get(cache_key)
        if cached:
            print(f"[Cache HIT] {cache_key}")
            return pickle.loads(cached)

        print(f"[Cache MISS] {cache_key}")

        # Execute handler
        response = await next()

        # Store in cache
        await self.redis.setex(cache_key, 300, pickle.dumps(response))

        return response


class AsyncTransactionBehavior:
    def __init__(self, async_session):
        self.session = async_session

    async def __call__(self, request, next):
        async with self.session.begin():
            response = await next()
            # Transaction commits automatically
            return response

# Async handler
class AsyncGetUserHandler(Handler[GetUserRequest]):
    def __init__(self, async_db):
        self.db = async_db

    async def __call__(self, request: GetUserRequest) -> GetUserResponse:
        user = await self.db.get_user(request.user_id)
        return GetUserResponse(
            user_id=user.id,
            username=user.username,
            email=user.email
        )

# Compose async pipeline
async_db = AsyncDatabase()
redis_client = AsyncRedis()

handler = AsyncGetUserHandler(async_db)
pipeline = Pipeline(
    behaviors=[
        AsyncLoggingBehavior(),
        AsyncCachingBehavior(redis_client),
        AsyncTransactionBehavior(async_db.session),
    ],
    handler=handler
)

# Use async pipeline
async def main():
    response = await pipeline(GetUserRequest(user_id=123))
    print(f"User: {response.username}")

asyncio.run(main())
```

## Complete E-Commerce Example

```python
from dataclasses import dataclass
from datetime import datetime
from pymediate import Handler, Request, Mediator, Services
from pymediate.pipeline import Pipeline

# Domain models
@dataclass
class OrderCreatedResponse:
    order_id: int
    total_amount: float
    created_at: datetime
    status: str

@dataclass
class CreateOrderRequest(Request[OrderCreatedResponse]):
    user_id: int
    items: list[dict]
    payment_method: str
    auth_token: str

# Behaviors
class AuditBehavior:
    """Logs all operations for compliance."""

    def __init__(self, audit_log):
        self.audit_log = audit_log

    def __call__(self, request, next):
        request_id = self._generate_id()

        self.audit_log.log({
            'request_id': request_id,
            'type': type(request).__name__,
            'timestamp': datetime.now(),
            'user_id': getattr(request, 'user_id', None),
        })

        try:
            response = next()
            self.audit_log.log({
                'request_id': request_id,
                'status': 'success',
                'response': str(response)
            })
            return response
        except Exception as e:
            self.audit_log.log({
                'request_id': request_id,
                'status': 'error',
                'error': str(e)
            })
            raise


class RateLimitBehavior:
    """Prevents abuse with rate limiting."""

    def __init__(self, redis_client, max_requests=100, window=60):
        self.redis = redis_client
        self.max_requests = max_requests
        self.window = window

    def __call__(self, request, next):
        user_id = request.user_id
        key = f"rate_limit:user:{user_id}"

        current = int(self.redis.get(key) or 0)

        if current >= self.max_requests:
            raise TooManyRequestsError(
                f"Rate limit exceeded: {current}/{self.max_requests}"
            )

        # Increment and set expiry
        pipe = self.redis.pipeline()
        pipe.incr(key)
        pipe.expire(key, self.window)
        pipe.execute()

        return next()

# Handler
class CreateOrderHandler(Handler[CreateOrderRequest]):
    def __init__(self, database, payment_service):
        self.database = database
        self.payment_service = payment_service

    def __call__(self, request: CreateOrderRequest) -> OrderCreatedResponse:
        # Calculate total
        total = sum(item['price'] * item['quantity'] for item in request.items)

        # Process payment
        payment = self.payment_service.charge(
            amount=total,
            method=request.payment_method
        )

        # Create order
        order_id = self.database.create_order(
            user_id=request.user_id,
            items=request.items,
            total=total,
            payment_id=payment.id
        )

        return OrderCreatedResponse(
            order_id=order_id,
            total_amount=total,
            created_at=datetime.now(),
            status="confirmed"
        )

# Setup complete pipeline
database = Database()
payment_service = PaymentService()
redis_client = Redis()
logger = Logger()
audit_log = AuditLog()
token_service = TokenService()
metrics = MetricsCollector()

handler = CreateOrderHandler(database, payment_service)

pipeline = Pipeline(
    behaviors=[
        LoggingBehavior(logger),                      # Log everything
        PerformanceMonitoringBehavior(metrics),       # Track performance
        AuthenticationBehavior(token_service),        # Verify token
        RateLimitBehavior(redis_client),              # Prevent abuse
        ValidationBehavior(),                          # Validate input
        AuditBehavior(audit_log),                     # Compliance logging
        TransactionBehavior(database.session),        # Wrap in transaction
    ],
    handler=handler
)

# Register with mediator
services = Services()
services.add(CreateOrderRequest, pipeline)
mediator = Mediator(services.provider())

# Use it
response = mediator.send(CreateOrderRequest(
    user_id=123,
    items=[
        {'product_id': 456, 'quantity': 2, 'price': 29.99},
        {'product_id': 789, 'quantity': 1, 'price': 49.99},
    ],
    payment_method='credit_card',
    auth_token='eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...'
))

print(f"Order created: {response.order_id}")
print(f"Total: ${response.total_amount:.2f}")
```

## See Also

- [Pipeline Behaviors Guide](../guide/pipeline-behaviors.md) - Comprehensive guide
- [Pipeline API Reference](../api/pipeline.md) - API documentation
- [Async Examples](async.md) - More async examples
