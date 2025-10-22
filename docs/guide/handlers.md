# Handlers

Handlers are the core execution units in PyMediate. They contain your business logic and are completely independent from each other and from the infrastructure that invokes them.

## Table of Contents

- [What Are Handlers?](#what-are-handlers)
- [Handler Independence](#handler-independence)
- [Basic Handler Structure](#basic-handler-structure)
- [Async Handlers](#async-handlers)
- [Deployment Flexibility](#deployment-flexibility)
- [Stateful vs Stateless](#stateful-vs-stateless)
- [Handler Composition](#handler-composition)
- [Testing Strategies](#testing-strategies)
- [Best Practices](#best-practices)
- [Common Patterns](#common-patterns)

## What Are Handlers?

A handler is a class that implements the `Handler[RequestType]` protocol. Its sole responsibility is to process a specific type of request and return a response.

```python
from dataclasses import dataclass
from pymediate import Handler, Request

@dataclass
class CreateUserResponse:
    user_id: int
    username: str

@dataclass
class CreateUserRequest(Request[CreateUserResponse]):
    username: str
    email: str

class CreateUserHandler(Handler[CreateUserRequest]):
    def __init__(self, database):
        self.database = database

    def __call__(self, request: CreateUserRequest) -> CreateUserResponse:
        # Business logic here
        user_id = self.database.insert_user(
            username=request.username,
            email=request.email
        )
        return CreateUserResponse(user_id=user_id, username=request.username)
```

### Key Characteristics

1. **Single Responsibility**: Each handler handles exactly one request type
2. **Type-Safe**: Generic type `Handler[RequestType]` ensures type safety
3. **Framework-Independent**: No dependency on web frameworks, CLI, or infrastructure
4. **Testable**: Can be tested in isolation without infrastructure

## Handler Independence

One of the most powerful features of PyMediate is that **handlers don't know about each other**. They only know about:

- The request they receive
- The response they return
- Their own dependencies (database, services, etc.)

### Why Independence Matters

```python
# ❌ BAD: Handlers calling other handlers directly
class CreateOrderHandler(Handler[CreateOrderRequest]):
    def __init__(self, create_user_handler, send_email_handler):
        self.create_user_handler = create_user_handler
        self.send_email_handler = send_email_handler

    def __call__(self, request: CreateOrderRequest) -> CreateOrderResponse:
        # Tight coupling to other handlers
        user = self.create_user_handler(CreateUserRequest(...))
        self.send_email_handler(SendEmailRequest(...))
        return CreateOrderResponse(...)

# ✅ GOOD: Handlers using the mediator
class CreateOrderHandler(Handler[CreateOrderRequest]):
    def __init__(self, mediator, database):
        self.mediator = mediator
        self.database = database

    def __call__(self, request: CreateOrderRequest) -> CreateOrderResponse:
        # Loose coupling through mediator
        user = self.mediator.send(CreateUserRequest(...))
        self.mediator.send(SendEmailRequest(...))

        order_id = self.database.create_order(user_id=user.user_id)
        return CreateOrderResponse(order_id=order_id)
```

### Benefits of Independence

1. **Change Deployment Without Breaking System**: Move a handler from synchronous API to async cloud function without affecting other handlers
2. **Independent Evolution**: Update one handler's implementation without touching others
3. **Easy Testing**: Test each handler in isolation
4. **Parallel Development**: Different teams can work on different handlers
5. **Reusability**: Use the same handler in different contexts (web, CLI, batch jobs)

## Basic Handler Structure

### Minimal Handler

```python
class SimpleHandler(Handler[SimpleRequest]):
    def __call__(self, request: SimpleRequest) -> SimpleResponse:
        return SimpleResponse(result="processed")
```

### Handler with Dependencies

```python
class UserServiceHandler(Handler[GetUserRequest]):
    def __init__(self, database, cache, logger):
        self.database = database
        self.cache = cache
        self.logger = logger

    def __call__(self, request: GetUserRequest) -> GetUserResponse:
        # Check cache first
        cached = self.cache.get(f"user:{request.user_id}")
        if cached:
            self.logger.info(f"Cache hit for user {request.user_id}")
            return GetUserResponse(**cached)

        # Query database
        user = self.database.get_user(request.user_id)

        # Update cache
        self.cache.set(f"user:{request.user_id}", user.to_dict())

        return GetUserResponse(
            user_id=user.id,
            username=user.username,
            email=user.email
        )
```

### Handler with Validation

```python
class CreateProductHandler(Handler[CreateProductRequest]):
    def __init__(self, database, validator):
        self.database = database
        self.validator = validator

    def __call__(self, request: CreateProductRequest) -> CreateProductResponse:
        # Validate business rules
        validation_result = self.validator.validate_product(
            name=request.name,
            price=request.price,
            category=request.category
        )

        if not validation_result.is_valid:
            raise ValueError(f"Invalid product: {validation_result.errors}")

        # Create product
        product_id = self.database.create_product(
            name=request.name,
            price=request.price,
            category=request.category
        )

        return CreateProductResponse(
            product_id=product_id,
            name=request.name,
            price=request.price
        )
```

## Async Handlers

PyMediate provides first-class async/await support through the `pymediate.aio` package for I/O-bound operations.

### Basic Async Handler

```python
import asyncio
from dataclasses import dataclass
from pymediate import Request
from pymediate.aio import Handler, Mediator

@dataclass
class FetchDataResponse:
    data: dict

@dataclass
class FetchDataRequest(Request[FetchDataResponse]):
    url: str

class AsyncFetchHandler(Handler[FetchDataRequest]):
    def __init__(self, http_client):
        self.http_client = http_client

    async def __call__(self, request: FetchDataRequest) -> FetchDataResponse:
        # Async I/O operation
        data = await self.http_client.get(request.url)
        return FetchDataResponse(data=data)
```

!!! note "Async vs Sync Imports"
    For async handlers, import from `pymediate.aio`:

    - **Sync**: `from pymediate import Handler, Mediator`
    - **Async**: `from pymediate.aio import Handler, Mediator`

    Requests are always imported from the main package: `from pymediate import Request`

### Async Handler with Multiple I/O Operations

```python
from pymediate.aio import Handler

class ProcessOrderHandler(Handler[ProcessOrderRequest]):
    def __init__(self, payment_service, inventory_service, email_service):
        self.payment_service = payment_service
        self.inventory_service = inventory_service
        self.email_service = email_service

    async def __call__(self, request: ProcessOrderRequest) -> ProcessOrderResponse:
        # Run multiple async operations concurrently
        payment_result, inventory_result = await asyncio.gather(
            self.payment_service.charge(request.payment_info),
            self.inventory_service.reserve(request.items)
        )

        if not payment_result.success:
            # Rollback inventory
            await self.inventory_service.release(request.items)
            raise PaymentFailedError(payment_result.error)

        # Send confirmation email asynchronously
        await self.email_service.send_order_confirmation(
            email=request.customer_email,
            order_id=payment_result.order_id
        )

        return ProcessOrderResponse(
            order_id=payment_result.order_id,
            status="completed"
        )
```

### Using Async Handlers with Mediator

```python
from pymediate import SimpleResolver
from pymediate.aio import Mediator

# Setup async mediator
resolver = SimpleResolver()
resolver.register(FetchDataRequest, AsyncFetchHandler(http_client))
mediator = Mediator(resolver)

# Use with asyncio
async def main():
    response = await mediator.send(FetchDataRequest(url="https://api.example.com/data"))
    print(response.data)

asyncio.run(main())

# Or in async context
async def process():
    result1 = await mediator.send(FetchDataRequest(url="..."))
    result2 = await mediator.send(ProcessOrderRequest(...))
    return result1, result2
```

For more async examples, see the [Async/Await guide](../examples/async.md).

## Deployment Flexibility

One of the most powerful features of handler independence is **deployment flexibility**. The same handler can run in different environments without code changes.

### Example: Moving from API to Cloud Function

```python
# Same handler code works everywhere
class ProcessImageHandler(Handler[ProcessImageRequest]):
    def __init__(self, image_processor, storage):
        self.image_processor = image_processor
        self.storage = storage

    def __call__(self, request: ProcessImageRequest) -> ProcessImageResponse:
        # Business logic
        image_data = self.storage.download(request.image_url)
        processed = self.image_processor.resize(image_data, request.width, request.height)
        processed_url = self.storage.upload(processed)

        return ProcessImageResponse(processed_url=processed_url)
```

### Deployment 1: REST API (Flask)

```python
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/api/process-image', methods=['POST'])
def process_image():
    data = request.json

    # Use handler in API context
    req = ProcessImageRequest(
        image_url=data['image_url'],
        width=data['width'],
        height=data['height']
    )

    response = mediator.send(req)
    return jsonify({'processed_url': response.processed_url})
```

### Deployment 2: AWS Lambda

```python
import json

def lambda_handler(event, context):
    # Parse Lambda event
    body = json.loads(event['body'])

    # Same handler, different adapter
    req = ProcessImageRequest(
        image_url=body['image_url'],
        width=body['width'],
        height=body['height']
    )

    response = mediator.send(req)

    return {
        'statusCode': 200,
        'body': json.dumps({'processed_url': response.processed_url})
    }
```

### Deployment 3: Google Cloud Function

```python
def process_image_function(request):
    """Google Cloud Function entry point."""
    data = request.get_json()

    # Same handler, Google Cloud adapter
    req = ProcessImageRequest(
        image_url=data['image_url'],
        width=data['width'],
        height=data['height']
    )

    response = mediator.send(req)
    return {'processed_url': response.processed_url}
```

### Deployment 4: Azure Function

```python
import azure.functions as func

def main(req: func.HttpRequest) -> func.HttpResponse:
    data = req.get_json()

    # Same handler, Azure adapter
    request_obj = ProcessImageRequest(
        image_url=data['image_url'],
        width=data['width'],
        height=data['height']
    )

    response = mediator.send(request_obj)
    return func.HttpResponse(
        json.dumps({'processed_url': response.processed_url}),
        mimetype="application/json"
    )
```

### Deployment 5: Message Queue Consumer (Kafka)

```python
from kafka import KafkaConsumer

consumer = KafkaConsumer('image-processing-topic')

for message in consumer:
    data = json.loads(message.value)

    # Same handler, message queue adapter
    req = ProcessImageRequest(
        image_url=data['image_url'],
        width=data['width'],
        height=data['height']
    )

    response = mediator.send(req)

    # Publish result to another topic
    producer.send('processed-images-topic', {
        'original_url': req.image_url,
        'processed_url': response.processed_url
    })
```

### Deployment 6: CLI Tool

```python
import click

@click.command()
@click.option('--image-url', required=True)
@click.option('--width', type=int, required=True)
@click.option('--height', type=int, required=True)
def process_image_cli(image_url, width, height):
    """CLI tool using the same handler."""
    req = ProcessImageRequest(
        image_url=image_url,
        width=width,
        height=height
    )

    response = mediator.send(req)
    click.echo(f"Processed image: {response.processed_url}")
```

### Key Insight

**The handler code never changes**. Only the adapter (the thin layer that converts external input to requests) changes. This means:

- You can start with a simple Flask API
- Move to serverless (Lambda) for scalability
- Add CLI support for admin tools
- Add message queue processing for batch operations

All without touching your business logic!

## Stateful vs Stateless

### Stateless Handlers (Recommended)

Stateless handlers don't maintain state between invocations. They're safer, easier to scale, and work well with serverless.

```python
class GetUserHandler(Handler[GetUserRequest]):
    def __init__(self, database):
        self.database = database  # Dependency, not state

    def __call__(self, request: GetUserRequest) -> GetUserResponse:
        # No instance state used or modified
        user = self.database.get_user(request.user_id)
        return GetUserResponse(
            user_id=user.id,
            username=user.username
        )
```

**Benefits:**
- Thread-safe by default
- Can be used as singleton
- Works in serverless environments
- Easy to test
- No side effects

### Stateful Handlers (Use With Caution)

Stateful handlers maintain state between invocations. Use only when necessary.

```python
class RateLimitHandler(Handler[RateLimitRequest]):
    def __init__(self, max_requests: int):
        self.max_requests = max_requests
        self.request_counts: dict[str, int] = {}

    def __call__(self, request: RateLimitRequest) -> RateLimitResponse:
        # Modifies instance state
        current_count = self.request_counts.get(request.user_id, 0)

        if current_count >= self.max_requests:
            return RateLimitResponse(allowed=False, remaining=0)

        self.request_counts[request.user_id] = current_count + 1
        remaining = self.max_requests - (current_count + 1)

        return RateLimitResponse(allowed=True, remaining=remaining)
```

**Considerations:**
- Not thread-safe (need locks)
- State lost in serverless environments
- Can't use as singleton safely
- Hard to test (state pollution)
- Use external state store instead (Redis, database)

**Better Approach:**

```python
class RateLimitHandler(Handler[RateLimitRequest]):
    def __init__(self, redis_client, max_requests: int):
        self.redis = redis_client  # External state
        self.max_requests = max_requests

    def __call__(self, request: RateLimitRequest) -> RateLimitResponse:
        # State in Redis, not instance
        key = f"rate_limit:{request.user_id}"
        current_count = int(self.redis.get(key) or 0)

        if current_count >= self.max_requests:
            return RateLimitResponse(allowed=False, remaining=0)

        self.redis.incr(key)
        self.redis.expire(key, 3600)  # 1 hour window

        remaining = self.max_requests - (current_count + 1)
        return RateLimitResponse(allowed=True, remaining=remaining)
```

## Handler Composition

Handlers can compose other operations through the mediator, not by direct coupling.

### Sequential Composition

```python
class PlaceOrderHandler(Handler[PlaceOrderRequest]):
    def __init__(self, mediator, database):
        self.mediator = mediator
        self.database = database

    def __call__(self, request: PlaceOrderRequest) -> PlaceOrderResponse:
        # Step 1: Validate inventory
        inventory_check = self.mediator.send(
            CheckInventoryRequest(items=request.items)
        )
        if not inventory_check.available:
            raise InsufficientInventoryError()

        # Step 2: Process payment
        payment = self.mediator.send(
            ProcessPaymentRequest(
                amount=request.total,
                payment_method=request.payment_method
            )
        )

        # Step 3: Create order
        order_id = self.database.create_order(
            items=request.items,
            payment_id=payment.payment_id
        )

        # Step 4: Send confirmation
        self.mediator.send(
            SendOrderConfirmationRequest(
                order_id=order_id,
                email=request.customer_email
            )
        )

        return PlaceOrderResponse(order_id=order_id)
```

### Parallel Composition (Async)

```python
class FetchDashboardHandler(Handler[FetchDashboardRequest]):
    def __init__(self, mediator):
        self.mediator = mediator

    async def __call__(self, request: FetchDashboardRequest) -> FetchDashboardResponse:
        # Fetch multiple data sources in parallel
        user_data, orders_data, analytics_data = await asyncio.gather(
            self.mediator.send(GetUserRequest(user_id=request.user_id)),
            self.mediator.send(GetUserOrdersRequest(user_id=request.user_id)),
            self.mediator.send(GetAnalyticsRequest(user_id=request.user_id))
        )

        return FetchDashboardResponse(
            user=user_data,
            orders=orders_data,
            analytics=analytics_data
        )
```

### Conditional Composition

```python
class ProcessSubscriptionHandler(Handler[ProcessSubscriptionRequest]):
    def __init__(self, mediator):
        self.mediator = mediator

    def __call__(self, request: ProcessSubscriptionRequest) -> ProcessSubscriptionResponse:
        # Check if user exists
        try:
            user = self.mediator.send(GetUserRequest(user_id=request.user_id))
        except UserNotFoundError:
            # Create new user if needed
            user = self.mediator.send(
                CreateUserRequest(
                    email=request.email,
                    name=request.name
                )
            )

        # Check for existing subscription
        existing = self.mediator.send(
            GetSubscriptionRequest(user_id=user.user_id)
        )

        if existing.subscription:
            # Update existing subscription
            result = self.mediator.send(
                UpdateSubscriptionRequest(
                    subscription_id=existing.subscription.id,
                    plan=request.plan
                )
            )
        else:
            # Create new subscription
            result = self.mediator.send(
                CreateSubscriptionRequest(
                    user_id=user.user_id,
                    plan=request.plan
                )
            )

        return ProcessSubscriptionResponse(subscription=result)
```

## Testing Strategies

### Unit Testing (Isolated)

```python
import pytest

def test_create_user_handler():
    # Mock dependencies
    mock_db = MockDatabase()
    handler = CreateUserHandler(database=mock_db)

    # Create request
    request = CreateUserRequest(
        username="testuser",
        email="test@example.com"
    )

    # Execute handler
    response = handler(request)

    # Verify response
    assert response.username == "testuser"
    assert response.user_id > 0

    # Verify database interaction
    assert mock_db.insert_user.called_once_with(
        username="testuser",
        email="test@example.com"
    )
```

### Integration Testing (With Mediator)

```python
def test_place_order_integration():
    # Setup real resolver with all handlers
    resolver = SimpleResolver()
    resolver.register(CheckInventoryRequest, CheckInventoryHandler(inventory_db))
    resolver.register(ProcessPaymentRequest, ProcessPaymentHandler(payment_service))
    resolver.register(SendOrderConfirmationRequest, EmailHandler(email_service))

    mediator = Mediator(resolver)

    # Handler under test
    handler = PlaceOrderHandler(mediator=mediator, database=order_db)

    # Execute
    request = PlaceOrderRequest(
        items=[{"sku": "ABC123", "quantity": 2}],
        total=99.99,
        payment_method="credit_card",
        customer_email="customer@example.com"
    )

    response = handler(request)

    # Verify end-to-end flow
    assert response.order_id > 0
    assert order_db.get_order(response.order_id) is not None
```

### Async Testing

```python
import pytest

@pytest.mark.asyncio
async def test_async_handler():
    mock_http = MockHttpClient()
    handler = AsyncFetchHandler(http_client=mock_http)

    request = FetchDataRequest(url="https://api.example.com/data")
    response = await handler(request)

    assert response.data is not None
    assert mock_http.get.called_once()
```

### Testing with Fixtures

```python
@pytest.fixture
def user_handler(database):
    return CreateUserHandler(database=database)

@pytest.fixture
def database():
    db = MockDatabase()
    yield db
    db.cleanup()

def test_with_fixtures(user_handler):
    request = CreateUserRequest(username="test", email="test@example.com")
    response = user_handler(request)
    assert response.user_id > 0
```

## Best Practices

### 1. Keep Handlers Focused

```python
# ✅ GOOD: Single responsibility
class CreateUserHandler(Handler[CreateUserRequest]):
    def __call__(self, request: CreateUserRequest) -> CreateUserResponse:
        user_id = self.database.create_user(request.username, request.email)
        return CreateUserResponse(user_id=user_id, username=request.username)

# ❌ BAD: Too many responsibilities
class CreateUserHandler(Handler[CreateUserRequest]):
    def __call__(self, request: CreateUserRequest) -> CreateUserResponse:
        user_id = self.database.create_user(request.username, request.email)
        self.send_welcome_email(request.email)  # Should be separate handler
        self.update_analytics(user_id)  # Should be separate handler
        self.notify_admin(user_id)  # Should be separate handler
        return CreateUserResponse(user_id=user_id, username=request.username)
```

### 2. Inject Dependencies, Don't Create Them

```python
# ✅ GOOD: Dependencies injected
class UserHandler(Handler[GetUserRequest]):
    def __init__(self, database, cache, logger):
        self.database = database
        self.cache = cache
        self.logger = logger

# ❌ BAD: Creating dependencies inside
class UserHandler(Handler[GetUserRequest]):
    def __init__(self):
        self.database = DatabaseConnection()  # Hard to test
        self.cache = RedisCache()  # Hard to mock
```

### 3. Return Rich Response Objects

```python
# ✅ GOOD: Rich response with all data
@dataclass
class CreateUserResponse:
    user_id: int
    username: str
    created_at: datetime
    email_verified: bool

# ❌ BAD: Primitive return
def __call__(self, request: CreateUserRequest) -> int:  # Just user_id
    return self.database.create_user(...)
```

### 4. Validate Early

```python
class CreateProductHandler(Handler[CreateProductRequest]):
    def __call__(self, request: CreateProductRequest) -> CreateProductResponse:
        # Validate at the start
        if request.price < 0:
            raise ValueError("Price must be non-negative")
        if not request.name:
            raise ValueError("Name is required")

        # Then process
        product_id = self.database.create_product(...)
        return CreateProductResponse(product_id=product_id)
```

### 5. Use Mediator for Handler Composition

```python
# ✅ GOOD: Loose coupling through mediator
class OrderHandler(Handler[CreateOrderRequest]):
    def __init__(self, mediator, database):
        self.mediator = mediator
        self.database = database

    def __call__(self, request: CreateOrderRequest) -> CreateOrderResponse:
        self.mediator.send(SendEmailRequest(...))

# ❌ BAD: Direct handler coupling
class OrderHandler(Handler[CreateOrderRequest]):
    def __init__(self, email_handler, database):
        self.email_handler = email_handler  # Tight coupling
        self.database = database

    def __call__(self, request: CreateOrderRequest) -> CreateOrderResponse:
        self.email_handler(SendEmailRequest(...))
```

### 6. Prefer Stateless Handlers

```python
# ✅ GOOD: Stateless with external storage
class SessionHandler(Handler[CreateSessionRequest]):
    def __init__(self, redis):
        self.redis = redis

    def __call__(self, request: CreateSessionRequest) -> CreateSessionResponse:
        session_id = generate_id()
        self.redis.set(f"session:{session_id}", request.user_id)
        return CreateSessionResponse(session_id=session_id)

# ❌ BAD: Stateful with instance variables
class SessionHandler(Handler[CreateSessionRequest]):
    def __init__(self):
        self.sessions = {}  # State in memory

    def __call__(self, request: CreateSessionRequest) -> CreateSessionResponse:
        session_id = generate_id()
        self.sessions[session_id] = request.user_id  # Lost on restart
        return CreateSessionResponse(session_id=session_id)
```

### 7. Use Type Hints Everywhere

```python
# ✅ GOOD: Full type hints
class Handler(Handler[MyRequest]):
    def __init__(self, database: Database, cache: Cache) -> None:
        self.database = database
        self.cache = cache

    def __call__(self, request: MyRequest) -> MyResponse:
        result: dict[str, Any] = self.database.query(...)
        return MyResponse(data=result)
```

## Common Patterns

### Command Pattern (No Response Needed)

```python
@dataclass
class LogEventResponse:
    success: bool

@dataclass
class LogEventRequest(Request[LogEventResponse]):
    event_type: str
    data: dict

class LogEventHandler(Handler[LogEventRequest]):
    def __init__(self, logger):
        self.logger = logger

    def __call__(self, request: LogEventRequest) -> LogEventResponse:
        self.logger.log(request.event_type, request.data)
        return LogEventResponse(success=True)
```

### Query Pattern (Read-Only)

```python
@dataclass
class GetProductsResponse:
    products: list[Product]
    total: int

@dataclass
class GetProductsRequest(Request[GetProductsResponse]):
    category: str
    page: int
    per_page: int

class GetProductsHandler(Handler[GetProductsRequest]):
    def __init__(self, database):
        self.database = database

    def __call__(self, request: GetProductsRequest) -> GetProductsResponse:
        # Read-only query
        products = self.database.get_products(
            category=request.category,
            limit=request.per_page,
            offset=request.page * request.per_page
        )
        total = self.database.count_products(category=request.category)
        return GetProductsResponse(products=products, total=total)
```

### Result Pattern (Success/Failure)

```python
@dataclass
class Result[T]:
    success: bool
    data: T | None
    error: str | None

@dataclass
class ProcessPaymentResponse:
    result: Result[Payment]

class ProcessPaymentHandler(Handler[ProcessPaymentRequest]):
    def __call__(self, request: ProcessPaymentRequest) -> ProcessPaymentResponse:
        try:
            payment = self.payment_service.charge(request.amount)
            return ProcessPaymentResponse(
                result=Result(success=True, data=payment, error=None)
            )
        except PaymentError as e:
            return ProcessPaymentResponse(
                result=Result(success=False, data=None, error=str(e))
            )
```

### Decorator Pattern (Handler Wrapping)

```python
class LoggingHandlerDecorator[T](Handler[T]):
    def __init__(self, inner_handler: Handler[T], logger):
        self.inner_handler = inner_handler
        self.logger = logger

    def __call__(self, request: T) -> Any:
        self.logger.info(f"Handling {type(request).__name__}")
        try:
            response = self.inner_handler(request)
            self.logger.info(f"Success: {type(response).__name__}")
            return response
        except Exception as e:
            self.logger.error(f"Error: {e}")
            raise

# Usage
handler = LoggingHandlerDecorator(
    inner_handler=CreateUserHandler(database),
    logger=logger
)
```

### Pipeline Pattern (Multi-Step)

```python
class PipelineHandler(Handler[PipelineRequest]):
    def __init__(self, mediator):
        self.mediator = mediator

    def __call__(self, request: PipelineRequest) -> PipelineResponse:
        # Step 1
        result1 = self.mediator.send(Step1Request(data=request.data))

        # Step 2 uses result from step 1
        result2 = self.mediator.send(Step2Request(data=result1.output))

        # Step 3 uses result from step 2
        result3 = self.mediator.send(Step3Request(data=result2.output))

        return PipelineResponse(final_result=result3.output)
```

---

## Next Steps

- Learn about [Mediator](mediator.md) - How to coordinate handlers
- Explore [Error Handling](error-handling.md) - Best practices for errors
- See [Examples](../examples/basic.md) - Real-world handler examples
- Read [Best Practices](../advanced/best-practices.md) - Advanced patterns
