# Mediator

The Mediator is the central orchestrator in PyMediate. It receives requests and routes them to the appropriate handlers, eliminating direct dependencies between components.

## Table of Contents

- [What is the Mediator?](#what-is-the-mediator)
- [Why Use the Mediator Pattern?](#why-use-the-mediator-pattern)
- [Basic Usage](#basic-usage)
- [How It Works](#how-it-works)
- [Async Support](#async-support)
- [Request Lifecycle](#request-lifecycle)
- [Error Handling](#error-handling)
- [Advanced Patterns](#advanced-patterns)
- [Testing with Mediator](#testing-with-mediator)
- [Best Practices](#best-practices)
- [Common Use Cases](#common-use-cases)

## What is the Mediator?

The Mediator is a simple but powerful class that:

1. **Receives requests** from your application (API, CLI, etc.)
2. **Finds the appropriate handler** using a service provider
3. **Executes the handler** with the request
4. **Returns the response** back to the caller

```python
from pymediate import Mediator, Services

# Create resolver with handlers
services = Services()
services.add(CreateUserHandler(database))

# Create mediator
mediator = Mediator(resolver)

# Send request
response = mediator.send(CreateUserRequest(username="alice", email="alice@example.com"))
```

### The Mediator Pattern

The mediator pattern is a behavioral design pattern that reduces coupling between components by having them communicate through a central mediator rather than directly with each other.

```
Without Mediator (Tight Coupling):
┌─────────┐     ┌─────────┐     ┌─────────┐
│Handler A│────▶│Handler B│────▶│Handler C│
└─────────┘     └─────────┘     └─────────┘
     │               │               │
     └───────────────┴───────────────┘
         All handlers know about each other

With Mediator (Loose Coupling):
┌─────────┐     ┌──────────┐     ┌─────────┐
│Handler A│────▶│          │◀────│Handler B│
└─────────┘     │ Mediator │     └─────────┘
                │          │
┌─────────┐     │          │     ┌─────────┐
│Handler C│────▶│          │◀────│Handler D│
└─────────┘     └──────────┘     └─────────┘
    Handlers only know about the mediator
```

## Why Use the Mediator Pattern?

### 1. Decoupling

Handlers don't know about each other. They only know about requests and responses.

```python
# Without mediator - tight coupling
class CreateOrderHandler:
    def __init__(self, payment_handler, email_handler, inventory_handler):
        self.payment_handler = payment_handler  # Knows about other handlers
        self.email_handler = email_handler
        self.inventory_handler = inventory_handler

    def handle(self, order):
        self.payment_handler.charge(order.payment)
        self.inventory_handler.reserve(order.items)
        self.email_handler.send(order.confirmation)

# With mediator - loose coupling
class CreateOrderHandler:
    def __init__(self, mediator, database):
        self.mediator = mediator  # Only knows about mediator
        self.database = database

    def __call__(self, request):
        self.mediator.send(ChargePaymentRequest(...))
        self.mediator.send(ReserveInventoryRequest(...))
        self.mediator.send(SendEmailRequest(...))
```

### 2. Single Responsibility

Each handler has one job. The mediator handles routing.

```python
# Handler only cares about its logic
class CreateUserHandler(Handler[CreateUserRequest]):
    def __call__(self, request: CreateUserRequest) -> CreateUserResponse:
        # Just create the user - mediator handles routing
        user_id = self.database.create_user(request.username, request.email)
        return CreateUserResponse(user_id=user_id, username=request.username)
```

### 3. Testability

Test handlers in isolation without complex setup.

```python
def test_create_user_handler():
    # No need to mock other handlers
    handler = CreateUserHandler(database=mock_db)
    response = handler(CreateUserRequest(username="test", email="test@example.com"))
    assert response.user_id > 0
```

### 4. Flexibility

Change handler implementations without affecting callers.

```python
# Start with simple resolver
services = Services()
services.add(SimpleUserHandler(database))

# Later, switch to DI container
from pymediate import DependencyInjectorServiceProvider
provider = DependencyInjectorServiceProvider(container)

# Mediator usage stays the same!
mediator = Mediator(resolver)
response = mediator.send(GetUserRequest(user_id=123))
```

## Basic Usage

### Setup

```python
from dataclasses import dataclass
from pymediate import Mediator, Services, Handler, Request

# 1. Define request and response
@dataclass
class CreateUserResponse:
    user_id: int
    username: str

@dataclass
class CreateUserRequest(Request[CreateUserResponse]):
    username: str
    email: str

# 2. Create handler
class CreateUserHandler(Handler[CreateUserRequest]):
    def __init__(self, database):
        self.database = database

    def __call__(self, request: CreateUserRequest) -> CreateUserResponse:
        user_id = self.database.create_user(request.username, request.email)
        return CreateUserResponse(user_id=user_id, username=request.username)

# 3. Setup resolver
services = Services()
services.add(CreateUserHandler(database))

# 4. Create mediator
mediator = Mediator(resolver)
```

### Sending Requests

```python
# Send request
request = CreateUserRequest(username="alice", email="alice@example.com")
response = mediator.send(request)

print(f"Created user {response.username} with ID {response.user_id}")
```

### Type Safety

The mediator preserves type information:

```python
# Type checker knows response is CreateUserResponse
response: CreateUserResponse = mediator.send(CreateUserRequest(...))

# Auto-completion works
print(response.user_id)  # ✅ Type checker knows this exists
print(response.invalid)   # ❌ Type checker catches this error
```

## How It Works

### Request Resolution Flow

```
1. Application sends request to mediator
   ↓
2. Mediator asks resolver for handler
   ↓
3. Resolver looks up handler by request type
   ↓
4. Mediator executes handler with request
   ↓
5. Handler returns response
   ↓
6. Mediator returns response to application
```

### Example with Multiple Handlers

```python
from pymediate import Mediator, Services

# Setup multiple handlers
services = Services()
services.add(CreateUserHandler(database))
services.add(GetUserHandler(database))
services.add(DeleteUserHandler(database))

mediator = Mediator(resolver)

# Mediator routes to correct handler based on request type
create_response = mediator.send(CreateUserRequest(...))  # → CreateUserHandler
get_response = mediator.send(GetUserRequest(...))        # → GetUserHandler
delete_response = mediator.send(DeleteUserRequest(...))  # → DeleteUserHandler
```

### Under the Hood

```python
class Mediator:
    def __init__(self, resolver: Resolver):
        self.service_provider = resolver

    def send[RequestT](self, request: RequestT):
        # 1. Get handler for this request type
        handler = self.service_provider.resolve(type(request))

        # 2. Execute handler
        if inspect.iscoroutinefunction(handler):
            return await handler(request)  # Async handler
        else:
            return handler(request)  # Sync handler
```

## Async Support

The mediator automatically detects and handles async handlers.

### Async Handler

```python
class FetchDataHandler(Handler[FetchDataRequest]):
    def __init__(self, http_client):
        self.http_client = http_client

    async def __call__(self, request: FetchDataRequest) -> FetchDataResponse:
        data = await self.http_client.get(request.url)
        return FetchDataResponse(data=data)
```

### Using Async with Mediator

```python
# Mediator automatically awaits async handlers
response = await mediator.send(FetchDataRequest(url="https://api.example.com/data"))
```

### Mixed Sync and Async

```python
# Same mediator can handle both sync and async handlers
services = Services()
services.add(CreateUserHandler(database))  # Sync
services.add(FetchDataHandler(http_client))  # Async

mediator = Mediator(resolver)

# Sync request
user = mediator.send(CreateUserRequest(...))

# Async request
data = await mediator.send(FetchDataRequest(...))
```

### Parallel Async Requests

```python
import asyncio

async def fetch_dashboard(user_id: int):
    # Execute multiple requests in parallel
    user, orders, analytics = await asyncio.gather(
        mediator.send(GetUserRequest(user_id=user_id)),
        mediator.send(GetOrdersRequest(user_id=user_id)),
        mediator.send(GetAnalyticsRequest(user_id=user_id))
    )

    return DashboardData(user=user, orders=orders, analytics=analytics)
```

## Request Lifecycle

### 1. Request Creation

```python
# Application creates request
request = CreateUserRequest(username="alice", email="alice@example.com")
```

### 2. Pre-Handler (Optional Middleware)

```python
# Custom mediator with logging
class LoggingMediator(Mediator):
    def send[RequestT](self, request: RequestT):
        print(f"Handling {type(request).__name__}")
        response = super().send(request)
        print(f"Completed {type(request).__name__}")
        return response
```

### 3. Handler Resolution

```python
# Mediator asks resolver for handler
handler = self.service_provider.resolve(type(request))
```

### 4. Handler Execution

```python
# Handler processes request
response = handler(request)
```

### 5. Post-Handler (Optional)

```python
# Can add post-processing in custom mediator
class ValidationMediator(Mediator):
    def send[RequestT](self, request: RequestT):
        response = super().send(request)
        self.validate_response(response)
        return response

    def validate_response(self, response):
        # Validate response structure
        if not hasattr(response, '__dataclass_fields__'):
            raise ValueError("Response must be a dataclass")
```

### 6. Response Return

```python
# Mediator returns response to caller
return response
```

## Error Handling

### Handler Not Found

```python
from pymediate import HandlerNotFoundError

try:
    response = mediator.send(UnregisteredRequest())
except HandlerNotFoundError as e:
    print(f"No handler for request: {e.request_type}")
    print(f"Available handlers: {e.available_handlers}")
```

### Handler Errors

```python
class CreateUserHandler(Handler[CreateUserRequest]):
    def __call__(self, request: CreateUserRequest) -> CreateUserResponse:
        if not request.email:
            raise ValueError("Email is required")

        user_id = self.database.create_user(request.username, request.email)
        return CreateUserResponse(user_id=user_id, username=request.username)

# Errors propagate naturally
try:
    response = mediator.send(CreateUserRequest(username="test", email=""))
except ValueError as e:
    print(f"Validation error: {e}")
```

### Custom Error Handling Mediator

```python
class ErrorHandlingMediator(Mediator):
    def __init__(self, resolver, logger):
        super().__init__(resolver)
        self.logger = logger

    def send[RequestT](self, request: RequestT):
        try:
            return super().send(request)
        except Exception as e:
            self.logger.error(f"Error handling {type(request).__name__}: {e}")
            raise
```

## Advanced Patterns

### Mediator with Middleware

```python
class MiddlewareMediator(Mediator):
    def __init__(self, resolver, middlewares=None):
        super().__init__(resolver)
        self.middlewares = middlewares or []

    def send[RequestT](self, request: RequestT):
        # Run pre-middlewares
        for middleware in self.middlewares:
            middleware.before(request)

        # Execute handler
        try:
            response = super().send(request)
        except Exception as e:
            # Run error middlewares
            for middleware in self.middlewares:
                middleware.on_error(request, e)
            raise

        # Run post-middlewares
        for middleware in self.middlewares:
            middleware.after(request, response)

        return response

# Usage
class LoggingMiddleware:
    def before(self, request):
        print(f"Before: {type(request).__name__}")

    def after(self, request, response):
        print(f"After: {type(response).__name__}")

    def on_error(self, request, error):
        print(f"Error in {type(request).__name__}: {error}")

mediator = MiddlewareMediator(
    resolver,
    middlewares=[LoggingMiddleware(), MetricsMiddleware()]
)
```

### Request Context

```python
from contextvars import ContextVar

request_context = ContextVar('request_context')

class ContextMediator(Mediator):
    def send[RequestT](self, request: RequestT):
        # Store request in context
        token = request_context.set({
            'request_id': generate_id(),
            'request_type': type(request).__name__,
            'timestamp': datetime.now()
        })

        try:
            return super().send(request)
        finally:
            request_context.reset(token)

# Handlers can access context
class CreateUserHandler(Handler[CreateUserRequest]):
    def __call__(self, request: CreateUserRequest) -> CreateUserResponse:
        ctx = request_context.get()
        print(f"Request ID: {ctx['request_id']}")
        # ... rest of handler
```

### Scoped Mediator

```python
class ScopedMediator(Mediator):
    """Mediator that creates new handler instances per request."""

    def send[RequestT](self, request: RequestT):
        # Get handler factory instead of instance
        handler_factory = self.service_provider.resolve(type(request))

        # Create new handler instance
        handler = handler_factory()

        # Execute
        return handler(request)
```

### Caching Mediator

```python
class CachingMediator(Mediator):
    def __init__(self, resolver, cache):
        super().__init__(resolver)
        self.cache = cache

    def send[RequestT](self, request: RequestT):
        # Only cache read-only queries
        if isinstance(request, Query):  # Assuming Query base class
            cache_key = self._get_cache_key(request)
            cached = self.cache.get(cache_key)
            if cached:
                return cached

        # Execute handler
        response = super().send(request)

        # Cache query responses
        if isinstance(request, Query):
            self.cache.set(cache_key, response, ttl=300)

        return response

    def _get_cache_key(self, request):
        return f"{type(request).__name__}:{hash(request)}"
```

### Transaction Mediator

```python
class TransactionMediator(Mediator):
    def __init__(self, resolver, database):
        super().__init__(resolver)
        self.database = database

    def send[RequestT](self, request: RequestT):
        # Start transaction for commands
        if isinstance(request, Command):  # Assuming Command base class
            with self.database.transaction():
                return super().send(request)
        else:
            return super().send(request)
```

## Testing with Mediator

### Unit Testing (Without Mediator)

```python
def test_handler_isolated():
    # Test handler directly without mediator
    handler = CreateUserHandler(database=mock_db)
    response = handler(CreateUserRequest(username="test", email="test@example.com"))
    assert response.user_id > 0
```

### Integration Testing (With Mediator)

```python
def test_with_mediator():
    # Test full request flow
    services = Services()
    services.add(CreateUserHandler(mock_db))

    mediator = Mediator(resolver)
    response = mediator.send(CreateUserRequest(username="test", email="test@example.com"))

    assert response.user_id > 0
    assert response.username == "test"
```

### Testing Handler Composition

```python
def test_handler_composition():
    # Setup all handlers
    services = Services()
    services.add(CreateUserHandler(mock_db))
    services.add(EmailHandler(mock_email))

    mediator = Mediator(resolver)

    # Handler that calls other handlers through mediator
    class CreateUserWithEmailHandler(Handler[CreateUserWithEmailRequest]):
        def __init__(self, mediator, database):
            self.mediator = mediator
            self.database = database

        def __call__(self, request):
            # Create user
            user = self.mediator.send(
                CreateUserRequest(username=request.username, email=request.email)
            )

            # Send email
            self.mediator.send(
                SendEmailRequest(to=request.email, subject="Welcome!")
            )

            return user

    # Test composition
    handler = CreateUserWithEmailHandler(mediator=mediator, database=mock_db)
    response = handler(CreateUserWithEmailRequest(...))

    assert response.user_id > 0
    assert mock_email.sent_count == 1
```

### Mock Mediator

```python
class MockMediator:
    def __init__(self):
        self.sent_requests = []

    def send(self, request):
        self.sent_requests.append(request)
        # Return mock response based on request type
        if isinstance(request, CreateUserRequest):
            return CreateUserResponse(user_id=999, username=request.username)
        # ... other request types

def test_with_mock_mediator():
    mock_mediator = MockMediator()
    handler = PlaceOrderHandler(mediator=mock_mediator, database=mock_db)

    response = handler(PlaceOrderRequest(...))

    # Verify handler sent expected requests
    assert len(mock_mediator.sent_requests) == 3
    assert isinstance(mock_mediator.sent_requests[0], ChargePaymentRequest)
    assert isinstance(mock_mediator.sent_requests[1], ReserveInventoryRequest)
    assert isinstance(mock_mediator.sent_requests[2], SendEmailRequest)
```

## Best Practices

### 1. One Mediator Instance Per Application

```python
# ✅ GOOD: Single mediator instance
# app.py
mediator = Mediator(resolver)

# Use same instance throughout application
app.state.mediator = mediator

# ❌ BAD: Creating multiple mediators
def handle_request():
    mediator = Mediator(resolver)  # Don't create per request
    return mediator.send(...)
```

### 2. Inject Mediator into Handlers

```python
# ✅ GOOD: Inject mediator
class CreateOrderHandler(Handler[CreateOrderRequest]):
    def __init__(self, mediator, database):
        self.mediator = mediator
        self.database = database

# ❌ BAD: Global mediator
global_mediator = Mediator(resolver)

class CreateOrderHandler(Handler[CreateOrderRequest]):
    def __call__(self, request):
        global_mediator.send(...)  # Hard to test
```

### 3. Don't Mix Mediator and Direct Handler Calls

```python
# ✅ GOOD: Consistent use of mediator
class OrderHandler(Handler[CreateOrderRequest]):
    def __init__(self, mediator):
        self.mediator = mediator

    def __call__(self, request):
        self.mediator.send(ChargePaymentRequest(...))
        self.mediator.send(SendEmailRequest(...))

# ❌ BAD: Mixing patterns
class OrderHandler(Handler[CreateOrderRequest]):
    def __init__(self, mediator, email_handler):
        self.mediator = mediator
        self.email_handler = email_handler

    def __call__(self, request):
        self.mediator.send(ChargePaymentRequest(...))
        self.email_handler(SendEmailRequest(...))  # Inconsistent
```

### 4. Keep Mediator Simple

```python
# ✅ GOOD: Simple mediator, complex logic in handlers
mediator = Mediator(resolver)

# ❌ BAD: Complex mediator with business logic
class BusinessLogicMediator(Mediator):
    def send(self, request):
        if isinstance(request, CreateUserRequest):
            # Validate email
            if '@' not in request.email:  # Business logic in mediator!
                raise ValueError("Invalid email")
        return super().send(request)
```

### 5. Use Type Hints

```python
# ✅ GOOD: Full type hints
def process_user_request(mediator: Mediator) -> CreateUserResponse:
    response: CreateUserResponse = mediator.send(
        CreateUserRequest(username="test", email="test@example.com")
    )
    return response
```

## Common Use Cases

### Web API

```python
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/api/users', methods=['POST'])
def create_user():
    data = request.json
    req = CreateUserRequest(username=data['username'], email=data['email'])
    response = mediator.send(req)
    return jsonify({'user_id': response.user_id, 'username': response.username})

@app.route('/api/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    req = GetUserRequest(user_id=user_id)
    response = mediator.send(req)
    return jsonify({'user_id': response.user_id, 'username': response.username})
```

### CLI Application

```python
import click

@click.group()
def cli():
    pass

@cli.command()
@click.option('--username', required=True)
@click.option('--email', required=True)
def create_user(username, email):
    """Create a new user."""
    req = CreateUserRequest(username=username, email=email)
    response = mediator.send(req)
    click.echo(f"Created user {response.username} with ID {response.user_id}")

@cli.command()
@click.argument('user_id', type=int)
def get_user(user_id):
    """Get user by ID."""
    req = GetUserRequest(user_id=user_id)
    response = mediator.send(req)
    click.echo(f"User: {response.username} (ID: {response.user_id})")
```

### Background Jobs

```python
from celery import Celery

app = Celery('tasks')

@app.task
def process_payment(payment_data):
    req = ProcessPaymentRequest(**payment_data)
    response = mediator.send(req)
    return {'payment_id': response.payment_id, 'status': response.status}

@app.task
def send_report():
    req = GenerateReportRequest(report_type='daily')
    response = mediator.send(req)
    return {'report_url': response.url}
```

### Message Queue Consumer

```python
from kafka import KafkaConsumer
import json

consumer = KafkaConsumer('user-events')

for message in consumer:
    event = json.loads(message.value)

    if event['type'] == 'user_created':
        req = SendWelcomeEmailRequest(
            user_id=event['user_id'],
            email=event['email']
        )
        mediator.send(req)

    elif event['type'] == 'order_placed':
        req = ProcessOrderRequest(
            order_id=event['order_id'],
            user_id=event['user_id']
        )
        mediator.send(req)
```

### GraphQL Resolver

```python
import strawberry

@strawberry.type
class Mutation:
    @strawberry.mutation
    def create_user(self, username: str, email: str) -> User:
        req = CreateUserRequest(username=username, email=email)
        response = mediator.send(req)
        return User(id=response.user_id, username=response.username)

@strawberry.type
class Query:
    @strawberry.field
    def user(self, user_id: int) -> User:
        req = GetUserRequest(user_id=user_id)
        response = mediator.send(req)
        return User(id=response.user_id, username=response.username)
```

---

## Next Steps

- Learn about [Dependency Injection](dependency-injection.md) - How to wire up handlers
- Explore [Handlers](handlers.md) - Writing handler implementations
- See [Error Handling](error-handling.md) - Handling errors gracefully
- Read [Examples](../examples/basic.md) - Real-world usage examples
