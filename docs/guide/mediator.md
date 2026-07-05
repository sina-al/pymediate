# Mediator

The Mediator is the central orchestrator in PyMediate. It receives requests and routes them to the appropriate handlers, eliminating direct dependencies between components.

## What is the mediator?

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
mediator = Mediator(services.provider())

# Send request
response = mediator.send(CreateUserRequest(username="alice", email="alice@example.com"))
```

### The mediator pattern

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

## Why use the mediator pattern?

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

### 2. Single responsibility

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
from pymediate.providers import DependencyInjectorServiceProvider
provider = DependencyInjectorServiceProvider(container)

# Mediator usage stays the same!
mediator = Mediator(services.provider())
response = mediator.send(GetUserRequest(user_id=123))
```

## Basic usage

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
mediator = Mediator(services.provider())
```

### Sending requests

```python
# Send request
request = CreateUserRequest(username="alice", email="alice@example.com")
response = mediator.send(request)

print(f"Created user {response.username} with ID {response.user_id}")
```

### Type safety

The mediator preserves type information:

```python
# Type checker knows response is CreateUserResponse
response: CreateUserResponse = mediator.send(CreateUserRequest(...))

# Auto-completion works
print(response.user_id)  # ✅ Type checker knows this exists
print(response.invalid)   # ❌ Type checker catches this error
```

## How it works

### Request resolution flow

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

### Example with multiple handlers

```python
from pymediate import Mediator, Services

# Setup multiple handlers
services = Services()
services.add(CreateUserHandler(database))
services.add(GetUserHandler(database))
services.add(DeleteUserHandler(database))

mediator = Mediator(services.provider())

# Mediator routes to correct handler based on request type
create_response = mediator.send(CreateUserRequest(...))  # → CreateUserHandler
get_response = mediator.send(GetUserRequest(...))        # → GetUserHandler
delete_response = mediator.send(DeleteUserRequest(...))  # → DeleteUserHandler
```

### Under the hood

```python
class Mediator:
    def __init__(self, services: ServiceProvider):
        self.services = services

    def send[RequestT](self, request: RequestT):
        # 1. Look up which handler class was registered for this request type
        #    (recorded automatically when the Handler[RequestT] subclass was defined)
        handler_class = registry.get_handler_class(type(request))

        # 2. Resolve a handler instance from the service provider
        handler = self.services.get(handler_class)

        # 3. Execute handler
        if inspect.iscoroutinefunction(handler.__call__):
            return await handler(request)  # Async handler
        else:
            return handler(request)  # Sync handler
```

## Async support

The mediator automatically detects and handles async handlers.

### Async handler

```python
class FetchDataHandler(Handler[FetchDataRequest]):
    def __init__(self, http_client):
        self.http_client = http_client

    async def __call__(self, request: FetchDataRequest) -> FetchDataResponse:
        data = await self.http_client.get(request.url)
        return FetchDataResponse(data=data)
```

### Using async with mediator

```python
# Mediator automatically awaits async handlers
response = await mediator.send(FetchDataRequest(url="https://api.example.com/data"))
```

### Mixed sync and async

```python
# Same mediator can handle both sync and async handlers
services = Services()
services.add(CreateUserHandler(database))  # Sync
services.add(FetchDataHandler(http_client))  # Async

mediator = Mediator(services.provider())

# Sync request
user = mediator.send(CreateUserRequest(...))

# Async request
data = await mediator.send(FetchDataRequest(...))
```

### Parallel async requests

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

## Request lifecycle

### 1. Request creation

```python
# Application creates request
request = CreateUserRequest(username="alice", email="alice@example.com")
```

### 2. Pipeline behaviors (optional middleware)

Pipeline behaviors are automatically discovered and applied to wrap request processing:

```python
from pymediate import Request, PipelineBehavior

# Define universal behavior - applies to all requests
class LoggingBehavior(PipelineBehavior[Request]):
    def __call__(self, request, next):
        print(f"Handling {type(request).__name__}")
        response = next()
        print(f"Completed {type(request).__name__}")
        return response

# Register behaviors - they're automatically applied to matching requests
services = Services()
services.add(LoggingBehavior())  # Auto-discovered! Applies to all requests
services.add(CreateUserHandler())
```

### 3. Behavior and handler resolution

```python
# Mediator resolves handler from registry
handler = self.services.get(handler_class)

# Mediator automatically discovers all registered behaviors
behaviors = self.services.get_all(PipelineBehavior)
```

### 4. Pipeline construction

```python
# If behaviors exist, mediator constructs a pipeline
if behaviors:
    pipeline = Pipeline(behaviors, handler)
else:
    # Fast path: call handler directly
    response = handler(request)
```

### 5. Request processing

```python
# Pipeline executes behaviors in order, then handler
response = pipeline(request)

# Execution flow:
# request → behavior1 → behavior2 → handler → response
#                                      ↓
#         behavior1 ← behavior2 ← handler
```

### 6. Response return

```python
# Mediator returns response to caller
return response
```

## Error handling

### Handler not found

```python
from pymediate import HandlerNotFoundError

try:
    response = mediator.send(UnregisteredRequest())
except HandlerNotFoundError as e:
    print(f"No handler for request: {e.request_type}")
    print(f"Available handlers: {e.available_handlers}")
```

### Handler errors

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

### Custom error-handling mediator

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

## Advanced patterns

### Mediator with pipeline behaviors

Pipeline behaviors provide a clean, composable way to add middleware to your mediator without subclassing. Behaviors are automatically discovered and applied to every request.

#### Simple example

```python
from pymediate import Request, PipelineBehavior, Services, Mediator

# Universal behaviors apply to all requests
class LoggingBehavior(PipelineBehavior[Request]):
    def __call__(self, request, next):
        print(f"Before: {type(request).__name__}")
        response = next()
        print(f"After: {type(request).__name__}")
        return response

class TimingBehavior(PipelineBehavior[Request]):
    def __call__(self, request, next):
        import time
        start = time.time()
        response = next()
        duration = time.time() - start
        print(f"Took {duration:.3f}s")
        return response

# Register behaviors - they apply to all requests automatically
services = Services()
services.add(LoggingBehavior())     # Outermost
services.add(TimingBehavior())      # Inner
services.add(CreateUserHandler())
services.add(GetUserHandler())

mediator = Mediator(services.provider())

# Every request goes through: Logging → Timing → Handler
response = mediator.send(CreateUserRequest(username="alice"))
```

#### With error handling

```python
class ErrorHandlingBehavior(PipelineBehavior[Request]):
    def __call__(self, request, next):
        try:
            return next()
        except Exception as e:
            print(f"Error in {type(request).__name__}: {e}")
            # Log to monitoring system, send alert, etc.
            raise  # Re-raise for caller to handle

class ValidationBehavior(PipelineBehavior[Request]):
    def __call__(self, request, next):
        # Pre-processing: validate request
        if hasattr(request, 'validate'):
            request.validate()
        return next()

services = Services()
services.add(ErrorHandlingBehavior())  # Catches all errors
services.add(ValidationBehavior())      # Validates requests
services.add(LoggingBehavior())         # Logs processing
services.add(CreateUserHandler())

mediator = Mediator(services.provider())
```

#### Why this approach

- No subclassing required.
- Behaviors are reusable across projects.
- Clear separation of concerns.
- Easy to test behaviors in isolation.
- Works with DI container scopes.
- Zero overhead when no behaviors are registered.

#### Execution order

```
Request
  → ErrorHandling (outermost)
    → Validation
      → Logging
        → Handler (innermost)
          → Response
      ← Logging
    ← Validation
  ← ErrorHandling (catches any errors)
```

See [Pipeline Behaviors Guide](pipeline-behaviors.md) for comprehensive documentation.

### Request context

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

### Scoped mediator

```python
class ScopedMediator(Mediator):
    """Mediator that creates new handler instances per request."""

    def send[RequestT](self, request: RequestT):
        # Get handler factory instead of instance
        handler_factory = self.services.get(type(request))

        # Create new handler instance
        handler = handler_factory()

        # Execute
        return handler(request)
```

### Caching mediator

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

### Transaction mediator

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

## Testing with mediator

### Unit testing (without mediator)

```python
def test_handler_isolated():
    # Test handler directly without mediator
    handler = CreateUserHandler(database=mock_db)
    response = handler(CreateUserRequest(username="test", email="test@example.com"))
    assert response.user_id > 0
```

### Integration testing (with mediator)

```python
def test_with_mediator():
    # Test full request flow
    services = Services()
    services.add(CreateUserHandler(mock_db))

    mediator = Mediator(services.provider())
    response = mediator.send(CreateUserRequest(username="test", email="test@example.com"))

    assert response.user_id > 0
    assert response.username == "test"
```

### Testing handler composition

```python
def test_handler_composition():
    # Setup all handlers
    services = Services()
    services.add(CreateUserHandler(mock_db))
    services.add(EmailHandler(mock_email))

    mediator = Mediator(services.provider())

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

### Mock mediator

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

## Best practices

### 1. One mediator instance per application

```python
# ✅ Good: Single mediator instance
# app.py
mediator = Mediator(services.provider())

# Use same instance throughout application
app.state.mediator = mediator

# ❌ Bad: Creating multiple mediators
def handle_request():
    mediator = Mediator(services.provider())  # Don't create per request
    return mediator.send(...)
```

### 2. Inject mediator into handlers

```python
# ✅ Good: Inject mediator
class CreateOrderHandler(Handler[CreateOrderRequest]):
    def __init__(self, mediator, database):
        self.mediator = mediator
        self.database = database

# ❌ Bad: Global mediator
global_mediator = Mediator(services.provider())

class CreateOrderHandler(Handler[CreateOrderRequest]):
    def __call__(self, request):
        global_mediator.send(...)  # Hard to test
```

### 3. Don't mix mediator and direct handler calls

```python
# ✅ Good: Consistent use of mediator
class OrderHandler(Handler[CreateOrderRequest]):
    def __init__(self, mediator):
        self.mediator = mediator

    def __call__(self, request):
        self.mediator.send(ChargePaymentRequest(...))
        self.mediator.send(SendEmailRequest(...))

# ❌ Bad: Mixing patterns
class OrderHandler(Handler[CreateOrderRequest]):
    def __init__(self, mediator, email_handler):
        self.mediator = mediator
        self.email_handler = email_handler

    def __call__(self, request):
        self.mediator.send(ChargePaymentRequest(...))
        self.email_handler(SendEmailRequest(...))  # Inconsistent
```

### 4. Keep mediator simple

```python
# ✅ Good: Simple mediator, complex logic in handlers
mediator = Mediator(services.provider())

# ❌ Bad: Complex mediator with business logic
class BusinessLogicMediator(Mediator):
    def send(self, request):
        if isinstance(request, CreateUserRequest):
            # Validate email
            if '@' not in request.email:  # Business logic in mediator!
                raise ValueError("Invalid email")
        return super().send(request)
```

### 5. Use type hints

```python
# ✅ Good: Full type hints
def process_user_request(mediator: Mediator) -> CreateUserResponse:
    response: CreateUserResponse = mediator.send(
        CreateUserRequest(username="test", email="test@example.com")
    )
    return response
```

## Common use cases

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

### CLI application

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

### Background jobs

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

### Message queue consumer

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

### GraphQL resolver

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

## Next steps

- Learn about [Dependency Injection](dependency-injection.md) - How to wire up handlers
- Explore [Handlers](handlers.md) - Writing handler implementations
- See [Error Handling](error-handling.md) - Handling errors gracefully
- Read [Examples](../examples/basic.md) - Real-world usage examples
