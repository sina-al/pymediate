# Requests and Responses

Requests and responses are the fundamental building blocks of PyMediate. They represent **messages** that flow through your application, completely independent of any delivery mechanism (HTTP, CLI, message queue, etc.).

## The Core Concept

At its heart, PyMediate encourages you to think of your application as a series of **requests** and **responses** (or **commands** and **queries** in CQRS terminology). This is a powerful architectural pattern that creates clear boundaries between your:

- **Core business logic** (domain layer)
- **Delivery mechanisms** (adapters/infrastructure)

```python
# This request represents "create a user" in your domain
# It knows NOTHING about HTTP, FastAPI, Flask, CLI, etc.
@dataclass
class CreateUserRequest(Request[UserCreated]):
    username: str
    email: str
    password: str

# The response represents the outcome
@dataclass
class UserCreated:
    user_id: int
    username: str
    created_at: datetime
```

## Framework Independence: The Hexagonal Architecture Principle

One of the most powerful aspects of the request/response pattern is **framework independence**. Your core application logic should not depend on Flask, FastAPI, Django, or any other framework.

### The Problem with Framework-Coupled Code

Traditional web applications often look like this:

```python
# ❌ BAD: Business logic coupled to Flask
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/users', methods=['POST'])
def create_user():
    # Business logic mixed with HTTP concerns
    data = request.get_json()
    username = data['username']
    email = data['email']

    # Validation mixed with HTTP
    if not username:
        return jsonify({'error': 'Username required'}), 400

    # Database access mixed with HTTP
    user_id = database.insert_user(username, email)

    # Response formation mixed with business logic
    return jsonify({'user_id': user_id, 'username': username}), 201
```

**Problems:**

- Can't reuse this logic in a CLI tool
- Can't test without HTTP mocking
- Can't switch to FastAPI without rewriting
- Can't run in a cloud function or message queue
- Business rules are scattered across routes

### The Solution: Request/Response Pattern

With PyMediate, your business logic is completely decoupled:

```python
# ✅ GOOD: Business logic independent of delivery mechanism

# 1. Domain layer - framework independent
@dataclass
class CreateUserRequest(Request[UserCreated]):
    """Pure business logic - no HTTP, no Flask, nothing."""
    username: str
    email: str
    password: str

@dataclass
class UserCreated:
    user_id: int
    username: str
    created_at: datetime

class CreateUserHandler(Handler[CreateUserRequest]):
    """Pure business logic - could run anywhere."""

    def __init__(self, user_repository: UserRepository):
        self.user_repository = user_repository

    def __call__(self, request: CreateUserRequest) -> UserCreated:
        # Pure business logic
        if not request.username:
            raise ValidationError("Username required")

        user = self.user_repository.create(
            username=request.username,
            email=request.email,
            password=hash_password(request.password)
        )

        return UserCreated(
            user_id=user.id,
            username=user.username,
            created_at=user.created_at
        )
```

Now you can use this **same code** with **any adapter**:

### Adapter 1: Flask

```python
# Flask adapter - just translates HTTP to requests
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/users', methods=['POST'])
def create_user_endpoint():
    """HTTP adapter - thin translation layer."""
    data = request.get_json()

    # Translate HTTP -> Domain Request
    domain_request = CreateUserRequest(
        username=data['username'],
        email=data['email'],
        password=data['password']
    )

    # Execute via mediator
    try:
        result = mediator.send(domain_request)

        # Translate Domain Response -> HTTP
        return jsonify({
            'user_id': result.user_id,
            'username': result.username,
            'created_at': result.created_at.isoformat()
        }), 201
    except ValidationError as e:
        return jsonify({'error': str(e)}), 400
```

### Adapter 2: FastAPI

```python
# FastAPI adapter - same business logic!
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

class CreateUserDTO(BaseModel):
    username: str
    email: str
    password: str

@app.post("/users")
async def create_user_endpoint(dto: CreateUserDTO):
    """Different framework, same business logic."""

    # Translate FastAPI model -> Domain Request
    domain_request = CreateUserRequest(
        username=dto.username,
        email=dto.email,
        password=dto.password
    )

    # Same mediator, same handler!
    try:
        result = mediator.send(domain_request)
        return {
            'user_id': result.user_id,
            'username': result.username,
            'created_at': result.created_at
        }
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

### Adapter 3: CLI

```python
# CLI adapter - no web framework needed!
import click

@click.command()
@click.option('--username', prompt=True)
@click.option('--email', prompt=True)
@click.password_option()
def create_user(username: str, email: str, password: str):
    """CLI adapter - same business logic."""

    # Translate CLI args -> Domain Request
    domain_request = CreateUserRequest(
        username=username,
        email=email,
        password=password
    )

    # Same handler, different entry point!
    try:
        result = mediator.send(domain_request)
        click.echo(f"✓ User created: {result.username} (ID: {result.user_id})")
    except ValidationError as e:
        click.echo(f"✗ Error: {e}", err=True)
```

### Adapter 4: AWS Lambda / Cloud Function

```python
# Cloud function adapter - runs in serverless!
def lambda_handler(event, context):
    """AWS Lambda adapter."""
    import json

    # Translate Lambda event -> Domain Request
    body = json.loads(event['body'])
    domain_request = CreateUserRequest(
        username=body['username'],
        email=body['email'],
        password=body['password']
    )

    # Same business logic, runs in the cloud!
    try:
        result = mediator.send(domain_request)
        return {
            'statusCode': 201,
            'body': json.dumps({
                'user_id': result.user_id,
                'username': result.username
            })
        }
    except ValidationError as e:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': str(e)})
        }
```

### Adapter 5: Message Queue Consumer

```python
# RabbitMQ/Kafka consumer - processes async messages
from kafka import KafkaConsumer
import json

consumer = KafkaConsumer('user-creation-topic')

for message in consumer:
    """Message queue adapter."""
    data = json.loads(message.value)

    # Translate message -> Domain Request
    domain_request = CreateUserRequest(
        username=data['username'],
        email=data['email'],
        password=data['password']
    )

    # Same handler, different trigger!
    try:
        result = mediator.send(domain_request)
        print(f"Processed user creation: {result.user_id}")
    except ValidationError as e:
        print(f"Validation error: {e}")
        # Send to dead letter queue
```

## The Power of Adapter Independence

Notice how:

1. **Business logic never changed** - `CreateUserHandler` is identical
2. **Same validation rules** - consistent across all adapters
3. **Same error handling** - domain errors handled consistently
4. **Easy testing** - test business logic without any framework
5. **Mix and match** - Use Flask for web, Kafka for async, Lambda for events

This is the essence of **Hexagonal Architecture** (also called Ports and Adapters):

- **Core (domain)**: Your requests, handlers, business logic
- **Ports**: The `Mediator` interface
- **Adapters**: Flask routes, FastAPI endpoints, CLI commands, Lambda functions

```
┌─────────────────────────────────────────────────────┐
│                                                     │
│           Adapters (Infrastructure)                 │
│                                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐         │
│  │  Flask   │  │ FastAPI  │  │   CLI    │         │
│  │  Routes  │  │Endpoints │  │ Commands │         │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘         │
│       │             │             │                │
│       └─────────────┴─────────────┘                │
│                     │                              │
│              ┌──────▼──────┐                       │
│              │             │                       │
│              │  Mediator   │  (Port)               │
│              │             │                       │
│              └──────┬──────┘                       │
│                     │                              │
│       ┌─────────────┴─────────────┐                │
│       │                           │                │
│  ┌────▼─────┐              ┌──────▼──────┐        │
│  │ Requests │              │  Handlers   │        │
│  │          │              │             │        │
│  │ Domain   │              │  Business   │        │
│  │ Messages │              │  Logic      │        │
│  └──────────┘              └─────────────┘        │
│                                                     │
│            Core Domain (Framework Independent)      │
│                                                     │
└─────────────────────────────────────────────────────┘
```

## CQRS: Commands vs Queries

CQRS (Command Query Responsibility Segregation) is a pattern that separates operations that change state from those that read state.

### Commands

Commands **change state** and return minimal data:

```python
@dataclass
class CreateUserCommand(Request[UserCreated]):
    """Command: Creates a user (write operation)."""
    username: str
    email: str
    password: str

@dataclass
class DeleteUserCommand(Request[UserDeleted]):
    """Command: Deletes a user (write operation)."""
    user_id: int

@dataclass
class UpdateUserEmailCommand(Request[EmailUpdated]):
    """Command: Updates email (write operation)."""
    user_id: int
    new_email: str
```

### Queries

Queries **read state** and return rich data:

```python
@dataclass
class GetUserQuery(Request[UserDetails]):
    """Query: Retrieves user data (read operation)."""
    user_id: int

@dataclass
class SearchUsersQuery(Request[UserList]):
    """Query: Searches users (read operation)."""
    search_term: str
    page: int = 1
    page_size: int = 20

@dataclass
class GetUserStatisticsQuery(Request[UserStatistics]):
    """Query: Gets user statistics (read operation)."""
    user_id: int
```

### Benefits of CQRS

1. **Clear Intent**: Method names make it obvious what happens
2. **Optimized Operations**: Can optimize reads and writes separately
3. **Scalability**: Can scale read and write databases independently
4. **Audit Trail**: Commands are perfect for event sourcing
5. **Caching**: Queries can be aggressively cached

```python
# Example: Separate read/write databases
class CreateUserHandler(Handler[CreateUserCommand]):
    """Writes to primary database."""
    def __init__(self, write_db: WriteDatabase):
        self.write_db = write_db

    def __call__(self, request: CreateUserCommand) -> UserCreated:
        return self.write_db.create_user(...)

class GetUserHandler(Handler[GetUserQuery]):
    """Reads from read-optimized replica."""
    def __init__(self, read_db: ReadDatabase):
        self.read_db = read_db

    def __call__(self, request: GetUserQuery) -> UserDetails:
        return self.read_db.get_user(request.user_id)
```

## Request Design Patterns

### 1. Immutable Value Objects

Requests should be immutable to prevent bugs:

```python
# ✓ Good - frozen dataclass (immutable)
@dataclass(frozen=True)
class TransferMoneyRequest(Request[TransferCompleted]):
    from_account: str
    to_account: str
    amount: Decimal

# ✗ Bad - mutable state
class TransferMoneyRequest(Request[TransferCompleted]):
    def __init__(self):
        self.from_account = None  # Can be changed!
        self.to_account = None
```

### 2. Rich Domain Validation

Include business rules in your requests:

```python
@dataclass
class CreateOrderRequest(Request[OrderCreated]):
    customer_id: int
    items: list[OrderItem]
    shipping_address: Address
    discount_code: str | None = None

    def __post_init__(self):
        """Validate at request creation time."""
        if not self.items:
            raise ValueError("Order must have at least one item")

        if len(self.items) > 100:
            raise ValueError("Order cannot exceed 100 items")

        total = sum(item.price * item.quantity for item in self.items)
        if total > 10000:
            raise ValueError("Order value exceeds maximum allowed")
```

### 3. Request Versioning

Handle API evolution with versioned requests:

```python
# Version 1
@dataclass
class CreateUserRequestV1(Request[UserCreated]):
    username: str
    email: str

# Version 2 - added optional field
@dataclass
class CreateUserRequestV2(Request[UserCreated]):
    username: str
    email: str
    phone: str | None = None

# Adapter can translate V1 -> V2
def translate_v1_to_v2(v1: CreateUserRequestV1) -> CreateUserRequestV2:
    return CreateUserRequestV2(
        username=v1.username,
        email=v1.email,
        phone=None
    )
```

### 4. Nested Value Objects

Use composition for complex domains:

```python
@dataclass(frozen=True)
class Address:
    street: str
    city: str
    postal_code: str
    country: str

@dataclass(frozen=True)
class OrderItem:
    product_id: str
    quantity: int
    price: Decimal

@dataclass(frozen=True)
class CreateOrderRequest(Request[OrderCreated]):
    customer_id: int
    items: list[OrderItem]
    shipping_address: Address
    billing_address: Address
```

## Response Design Patterns

### 1. Rich Response Objects

Return all data the caller might need:

```python
@dataclass
class UserCreated:
    """Rich response with everything needed."""
    user_id: int
    username: str
    email: str
    created_at: datetime
    activation_token: str  # For sending email
    profile_url: str  # For redirect
    is_email_verified: bool
```

### 2. Result Objects (Success/Failure)

Explicit success/failure handling:

```python
@dataclass
class PaymentResult:
    """Explicit result type."""
    success: bool
    transaction_id: str | None
    error_message: str | None
    error_code: str | None
    retry_allowed: bool

class ProcessPaymentHandler(Handler[ProcessPaymentRequest]):
    def __call__(self, request: ProcessPaymentRequest) -> PaymentResult:
        try:
            tx_id = self.payment_gateway.charge(request.amount)
            return PaymentResult(
                success=True,
                transaction_id=tx_id,
                error_message=None,
                error_code=None,
                retry_allowed=False
            )
        except InsufficientFundsError as e:
            return PaymentResult(
                success=False,
                transaction_id=None,
                error_message=str(e),
                error_code="INSUFFICIENT_FUNDS",
                retry_allowed=False
            )
        except NetworkError as e:
            return PaymentResult(
                success=False,
                transaction_id=None,
                error_message=str(e),
                error_code="NETWORK_ERROR",
                retry_allowed=True  # Can retry
            )
```

### 3. Pagination

Handle large datasets:

```python
@dataclass
class PaginatedUsers:
    users: list[UserSummary]
    total_count: int
    page: int
    page_size: int
    has_next: bool
    has_previous: bool

@dataclass
class ListUsersQuery(Request[PaginatedUsers]):
    page: int = 1
    page_size: int = 20
    search_term: str | None = None
    sort_by: str = "created_at"
    sort_order: str = "desc"
```

## Testing Without Frameworks

Framework independence makes testing trivial:

```python
def test_create_user():
    """Test business logic directly - no HTTP, no mocking!"""

    # Arrange
    fake_repo = InMemoryUserRepository()
    handler = CreateUserHandler(fake_repo)

    # Act
    request = CreateUserRequest(
        username="alice",
        email="alice@example.com",
        password="secret123"
    )
    result = handler(request)

    # Assert
    assert result.username == "alice"
    assert fake_repo.count() == 1

def test_validation():
    """Test validation without any framework."""
    fake_repo = InMemoryUserRepository()
    handler = CreateUserHandler(fake_repo)

    with pytest.raises(ValidationError):
        request = CreateUserRequest(
            username="",  # Invalid!
            email="alice@example.com",
            password="secret123"
        )
        handler(request)
```

## Real-World Example: E-commerce

Complete example showing framework independence:

```python
# Domain Layer - Framework Independent
@dataclass(frozen=True)
class PlaceOrderRequest(Request[OrderPlaced]):
    customer_id: int
    items: list[OrderItem]
    shipping_address: Address
    payment_method: PaymentMethod

@dataclass
class OrderPlaced:
    order_id: str
    total_amount: Decimal
    estimated_delivery: datetime
    confirmation_email_sent: bool

class PlaceOrderHandler(Handler[PlaceOrderRequest]):
    """Core business logic - runs anywhere."""

    def __init__(
        self,
        order_repo: OrderRepository,
        inventory: InventoryService,
        payment: PaymentService,
        email: EmailService
    ):
        self.order_repo = order_repo
        self.inventory = inventory
        self.payment = payment
        self.email = email

    def __call__(self, request: PlaceOrderRequest) -> OrderPlaced:
        # 1. Check inventory
        for item in request.items:
            if not self.inventory.is_available(item.product_id, item.quantity):
                raise OutOfStockError(item.product_id)

        # 2. Calculate total
        total = sum(item.price * item.quantity for item in request.items)

        # 3. Process payment
        transaction = self.payment.charge(request.payment_method, total)

        # 4. Create order
        order = self.order_repo.create(
            customer_id=request.customer_id,
            items=request.items,
            total=total,
            transaction_id=transaction.id
        )

        # 5. Reserve inventory
        for item in request.items:
            self.inventory.reserve(item.product_id, item.quantity)

        # 6. Send confirmation
        email_sent = self.email.send_order_confirmation(order)

        return OrderPlaced(
            order_id=order.id,
            total_amount=total,
            estimated_delivery=order.estimated_delivery,
            confirmation_email_sent=email_sent
        )
```

**Web API Adapter:**

```python
@app.post("/orders")
async def place_order_web(dto: PlaceOrderDTO):
    request = PlaceOrderRequest(
        customer_id=dto.customer_id,
        items=dto.items,
        shipping_address=dto.shipping_address,
        payment_method=dto.payment_method
    )

    result = mediator.send(request)
    return {"order_id": result.order_id}
```

**Scheduled Job:**

```python
@scheduler.task
def process_abandoned_carts():
    """Runs every hour - same business logic!"""
    for cart in cart_repo.find_abandoned():
        if cart.has_saved_payment():
            request = PlaceOrderRequest(
                customer_id=cart.customer_id,
                items=cart.items,
                shipping_address=cart.shipping_address,
                payment_method=cart.saved_payment_method
            )

            try:
                mediator.send(request)
            except OutOfStockError:
                email.send_out_of_stock_notification(cart.customer_id)
```

## Best Practices

### 1. Keep Requests Simple

```python
# ✓ Good - simple data transfer
@dataclass
class UpdateUserEmailRequest(Request[EmailUpdated]):
    user_id: int
    new_email: str

# ✗ Bad - too much logic
class UpdateUserEmailRequest(Request[EmailUpdated]):
    def __init__(self, user_id: int, new_email: str):
        self.user_id = user_id
        self.new_email = new_email
        self.validated = self.validate()  # Don't do this
```

### 2. Use Type Hints

```python
# ✓ Good - clear types
@dataclass
class SearchProductsQuery(Request[ProductList]):
    search_term: str
    min_price: Decimal | None
    max_price: Decimal | None
    categories: list[str]

# ✗ Bad - unclear types
class SearchProductsQuery(Request[ProductList]):
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
```

### 3. Namespace by Feature

```python
# Organize by business capability
app/
    orders/
        requests.py
        handlers.py
    users/
        requests.py
        handlers.py
    payments/
        requests.py
        handlers.py
```

## See Also

- [Handlers](handlers.md) - Implementing business logic
- [Hexagonal Architecture](../advanced/architecture.md) - Architectural patterns
- [Testing](../advanced/testing.md) - Testing strategies
