# Dataclasses with PyMediate

PyMediate has first-class support for Python dataclasses, making it easy to create type-safe, validated requests and responses with minimal boilerplate.

## Why dataclasses?

Dataclasses provide several benefits for PyMediate applications:

1. **Type safety.** Full mypy/pyright support with type hints.
2. **Less boilerplate.** Auto-generated `__init__`, `__repr__`, `__eq__`.
3. **Immutability.** Use `frozen=True` for immutable requests.
4. **Validation.** Use `__post_init__` for custom validation.
5. **IDE support.** Better auto-completion and refactoring.
6. **Serialization.** Easy JSON/dict conversion.

```python
from dataclasses import dataclass
from pymediate import Request

# Just 5 lines of code!
@dataclass
class CreateUserResponse:
    user_id: int
    username: str

@dataclass
class CreateUserRequest(Request[CreateUserResponse]):
    username: str
    email: str
```

Compare to manual class definition.

```python
# Without dataclasses - verbose and error-prone
class CreateUserRequest(Request[CreateUserResponse]):
    def __init__(self, username: str, email: str):
        self.username = username
        self.email = email

    def __repr__(self):
        return f"CreateUserRequest(username={self.username!r}, email={self.email!r})"

    def __eq__(self, other):
        if not isinstance(other, CreateUserRequest):
            return False
        return self.username == other.username and self.email == other.email
```

## Basic usage

### Minimal example

```python
from dataclasses import dataclass
from pymediate import Request, Handler

@dataclass
class HelloResponse:
    message: str

@dataclass
class HelloRequest(Request[HelloResponse]):
    name: str

class HelloHandler(Handler[HelloRequest]):
    def __call__(self, request: HelloRequest) -> HelloResponse:
        return HelloResponse(message=f"Hello, {request.name}!")
```

### Type hints are required

```python
# ✅ Good: Type hints present
@dataclass
class UserRequest(Request[UserResponse]):
    username: str  # Type hint required
    age: int       # Type hint required

# ❌ Bad: Missing type hints
@dataclass
class UserRequest(Request[UserResponse]):
    username       # Error: type hint required
    age           # Error: type hint required
```

## Request dataclasses

### Simple request

```python
@dataclass
class GetUserRequest(Request[UserResponse]):
    user_id: int
```

### Request with multiple fields

```python
@dataclass
class CreateProductRequest(Request[ProductResponse]):
    name: str
    description: str
    price: float
    category: str
    stock: int
    tags: list[str]
```

### Request with optional fields

```python
@dataclass
class UpdateUserRequest(Request[UserResponse]):
    user_id: int
    username: str | None = None
    email: str | None = None
    age: int | None = None
```

### Request with default values

```python
@dataclass
class SearchRequest(Request[SearchResponse]):
    query: str
    page: int = 1
    per_page: int = 10
    sort_by: str = "relevance"
```

## Response dataclasses

### Simple response

```python
@dataclass
class UserResponse:
    user_id: int
    username: str
```

### Rich response with multiple fields

```python
@dataclass
class ProductResponse:
    product_id: int
    name: str
    description: str
    price: float
    in_stock: bool
    created_at: datetime
    updated_at: datetime
    category: str
    tags: list[str]
    reviews_count: int
    average_rating: float
```

### Response with optional data

```python
@dataclass
class UserProfileResponse:
    user_id: int
    username: str
    email: str
    bio: str | None = None
    avatar_url: str | None = None
    location: str | None = None
```

### Response with status

```python
@dataclass
class OperationResponse:
    success: bool
    message: str
    error_code: str | None = None
    data: dict | None = None
```

### Exclude from repr

```python
from dataclasses import dataclass, field

@dataclass
class LoginRequest(Request[LoginResponse]):
    username: str
    password: str = field(repr=False)  # Don't print password in logs

print(LoginRequest(username="alice", password="secret123"))
# Output: LoginRequest(username='alice')
```

## Validation

### Basic validation with `__post_init__`

```python
@dataclass
class CreateUserRequest(Request[UserResponse]):
    username: str
    email: str
    age: int

    def __post_init__(self):
        if not self.username:
            raise ValueError("Username cannot be empty")
        if "@" not in self.email:
            raise ValueError("Invalid email format")
        if self.age < 0:
            raise ValueError("Age must be non-negative")
        if self.age < 18:
            raise ValueError("Must be 18 or older")
```

### Complex validation

```python
@dataclass
class CreateProductRequest(Request[ProductResponse]):
    name: str
    price: float
    category: str
    stock: int

    def __post_init__(self):
        # Validate name
        if len(self.name) < 3:
            raise ValueError("Product name must be at least 3 characters")
        if len(self.name) > 100:
            raise ValueError("Product name too long")

        # Validate price
        if self.price <= 0:
            raise ValueError("Price must be positive")
        if self.price > 1_000_000:
            raise ValueError("Price exceeds maximum allowed")

        # Validate category
        valid_categories = ["electronics", "clothing", "food", "books"]
        if self.category not in valid_categories:
            raise ValueError(f"Category must be one of: {valid_categories}")

        # Validate stock
        if self.stock < 0:
            raise ValueError("Stock cannot be negative")
```

### Data normalization in `__post_init__`

```python
@dataclass
class SearchRequest(Request[SearchResponse]):
    query: str
    filters: list[str]

    def __post_init__(self):
        # Normalize query (trim, lowercase)
        self.query = self.query.strip().lower()

        # Remove duplicates from filters
        self.filters = list(set(self.filters))
```

**For a frozen dataclass**, plain attribute assignment in `__post_init__` raises `FrozenInstanceError` — a frozen dataclass overrides `__setattr__` to block it. Use `object.__setattr__` to bypass that check for the one-time normalization.

```python
@dataclass(frozen=True)
class SearchRequest(Request[SearchResponse]):
    query: str
    filters: list[str]

    def __post_init__(self):
        object.__setattr__(self, "query", self.query.strip().lower())
        object.__setattr__(self, "filters", list(set(self.filters)))
```

## Frozen dataclasses

Frozen dataclasses are immutable - perfect for requests.

### Basic frozen request

```python
@dataclass(frozen=True)
class GetUserRequest(Request[UserResponse]):
    user_id: int

# Cannot modify after creation
req = GetUserRequest(user_id=123)
req.user_id = 456  # ❌ Error: cannot assign to field 'user_id'
```

### Benefits of frozen dataclasses

```python
@dataclass(frozen=True)
class CacheableRequest(Request[Response]):
    user_id: int
    include_details: bool

# Frozen dataclasses are hashable
requests_cache = {}
req = CacheableRequest(user_id=123, include_details=True)
requests_cache[req] = response  # ✅ Works! Can use as dict key

# Can use in sets
request_set = {req1, req2, req3}
```

### Frozen with mutable defaults (be careful)

```python
from dataclasses import dataclass, field

# ❌ Dangerous: Mutable default with frozen
@dataclass(frozen=True)
class FilterRequest(Request[FilterResponse]):
    filters: list[str] = []  # Don't do this!

# ✅ Correct: Use default_factory
@dataclass(frozen=True)
class FilterRequest(Request[FilterResponse]):
    filters: list[str] = field(default_factory=list)
```

## Nested dataclasses

### Simple nesting

```python
@dataclass
class Address:
    street: str
    city: str
    country: str
    postal_code: str

@dataclass
class CreateUserRequest(Request[UserResponse]):
    username: str
    email: str
    address: Address

# Usage
request = CreateUserRequest(
    username="alice",
    email="alice@example.com",
    address=Address(
        street="123 Main St",
        city="Springfield",
        country="USA",
        postal_code="12345"
    )
)
```

### Deep nesting

```python
@dataclass
class PaymentMethod:
    type: str  # "credit_card", "paypal", etc.
    details: dict

@dataclass
class ShippingAddress:
    street: str
    city: str
    postal_code: str

@dataclass
class OrderItem:
    product_id: int
    quantity: int
    price: float

@dataclass
class CreateOrderRequest(Request[OrderResponse]):
    user_id: int
    items: list[OrderItem]
    shipping_address: ShippingAddress
    payment_method: PaymentMethod
    notes: str | None = None

# Usage
request = CreateOrderRequest(
    user_id=123,
    items=[
        OrderItem(product_id=1, quantity=2, price=29.99),
        OrderItem(product_id=5, quantity=1, price=49.99)
    ],
    shipping_address=ShippingAddress(
        street="456 Oak Ave",
        city="Portland",
        postal_code="97201"
    ),
    payment_method=PaymentMethod(
        type="credit_card",
        details={"last_four": "1234"}
    )
)
```

### Nested validation

```python
@dataclass
class Coordinates:
    latitude: float
    longitude: float

    def __post_init__(self):
        if not -90 <= self.latitude <= 90:
            raise ValueError("Latitude must be between -90 and 90")
        if not -180 <= self.longitude <= 180:
            raise ValueError("Longitude must be between -180 and 180")

@dataclass
class LocationRequest(Request[LocationResponse]):
    name: str
    coords: Coordinates

    def __post_init__(self):
        # Parent validation runs after nested __post_init__
        if not self.name:
            raise ValueError("Name is required")
```

## Default values and factories

### Simple defaults

```python
@dataclass
class SearchRequest(Request[SearchResponse]):
    query: str
    page: int = 1
    per_page: int = 10
    sort: str = "relevance"
```

### Default factory for mutable types

```python
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class CreatePostRequest(Request[PostResponse]):
    title: str
    content: str
    tags: list[str] = field(default_factory=list)  # ✅ Correct
    metadata: dict = field(default_factory=dict)   # ✅ Correct
    created_at: datetime = field(default_factory=datetime.now)  # ✅ Correct

# ❌ Wrong: Mutable defaults
@dataclass
class BadRequest(Request[Response]):
    tags: list[str] = []  # All instances share same list!
    metadata: dict = {}   # All instances share same dict!
```

### Custom default factory

```python
import uuid
from datetime import datetime

def generate_request_id():
    return str(uuid.uuid4())

@dataclass
class TrackedRequest(Request[Response]):
    action: str
    request_id: str = field(default_factory=generate_request_id)
    timestamp: datetime = field(default_factory=datetime.now)

# Each instance gets unique ID and timestamp
req1 = TrackedRequest(action="create")
req2 = TrackedRequest(action="update")
assert req1.request_id != req2.request_id
```

## Dataclass mixins

### Timestamp mixin

```python
from dataclasses import dataclass
from datetime import datetime

@dataclass
class TimestampedMixin:
    created_at: datetime = field(default_factory=datetime.now)

@dataclass
class CreateUserRequest(TimestampedMixin, Request[UserResponse]):
    username: str
    email: str

# Request automatically has created_at
req = CreateUserRequest(username="alice", email="alice@example.com")
print(req.created_at)  # 2024-01-15 10:30:45.123456
```

### Validation mixin

```python
@dataclass
class EmailValidationMixin:
    email: str

    def __post_init__(self):
        if "@" not in self.email:
            raise ValueError("Invalid email format")
        super().__post_init__()  # Call parent if exists

@dataclass
class UserRequestBase(EmailValidationMixin, Request[UserResponse]):
    username: str
    email: str  # Will be validated by mixin

    def __post_init__(self):
        super().__post_init__()  # Calls EmailValidationMixin validation
        if len(self.username) < 3:
            raise ValueError("Username too short")
```

### Pagination mixin

```python
@dataclass
class PaginationMixin:
    page: int = 1
    per_page: int = 10

    def __post_init__(self):
        if self.page < 1:
            raise ValueError("Page must be >= 1")
        if self.per_page < 1 or self.per_page > 100:
            raise ValueError("Per page must be between 1 and 100")

@dataclass
class SearchUsersRequest(PaginationMixin, Request[SearchResponse]):
    query: str
    # Inherits page and per_page from PaginationMixin

# Usage
req = SearchUsersRequest(query="alice", page=2, per_page=20)
```

## Best practices

### 1. Always use type hints

```python
# ✅ Good: Full type hints
@dataclass
class UserRequest(Request[UserResponse]):
    user_id: int
    username: str
    email: str
    age: int | None = None

# ❌ Bad: Missing type hints
@dataclass
class UserRequest(Request[UserResponse]):
    user_id  # Error
    username  # Error
```

### 2. Use `frozen=True` for requests

```python
# ✅ Good: Immutable request
@dataclass(frozen=True)
class GetUserRequest(Request[UserResponse]):
    user_id: int

# ❌ Questionable: Mutable request
@dataclass
class GetUserRequest(Request[UserResponse]):
    user_id: int
```

### 3. Use `default_factory` for mutable defaults

```python
# ✅ Good: default_factory for lists/dicts
@dataclass
class FilterRequest(Request[FilterResponse]):
    tags: list[str] = field(default_factory=list)
    options: dict = field(default_factory=dict)

# ❌ Bad: Mutable default values
@dataclass
class FilterRequest(Request[FilterResponse]):
    tags: list[str] = []  # Shared between all instances!
    options: dict = {}    # Shared between all instances!
```

### 4. Validate in `__post_init__`

```python
# ✅ Good: Validation at creation time
@dataclass
class CreateUserRequest(Request[UserResponse]):
    email: str
    age: int

    def __post_init__(self):
        if "@" not in self.email:
            raise ValueError("Invalid email")
        if self.age < 18:
            raise ValueError("Must be 18+")

# ❌ Bad: Validation in handler
class CreateUserHandler(Handler[CreateUserRequest]):
    def __call__(self, request: CreateUserRequest) -> UserResponse:
        if "@" not in request.email:  # Too late!
            raise ValueError("Invalid email")
```

### 5. Use descriptive field names

```python
# ✅ Good: Clear field names
@dataclass
class SearchProductsRequest(Request[SearchResponse]):
    search_query: str
    min_price: float
    max_price: float
    category_id: int
    include_out_of_stock: bool

# ❌ Bad: Unclear abbreviations
@dataclass
class SearchProductsRequest(Request[SearchResponse]):
    q: str  # What does 'q' mean?
    min: float  # Min what?
    max: float  # Max what?
    cat: int  # Category?
    oos: bool  # Out of stock?
```

### 6. Group related fields with nested dataclasses

```python
# ✅ Good: Nested dataclasses
@dataclass
class PriceRange:
    min_price: float
    max_price: float

@dataclass
class SearchRequest(Request[SearchResponse]):
    query: str
    price_range: PriceRange
    category: str

# ❌ Questionable: Flat structure
@dataclass
class SearchRequest(Request[SearchResponse]):
    query: str
    min_price: float
    max_price: float
    category: str
```

### 7. Use `slots=True` for high-volume requests

```python
# ✅ Good: Slots for frequently created objects
@dataclass(slots=True, frozen=True)
class LogEventRequest(Request[LogResponse]):
    event_type: str
    timestamp: datetime
    data: dict

# Memory usage: ~40% less than regular dataclass
```

## Common patterns

### Result type

```python
@dataclass
class Success[T]:
    value: T

@dataclass
class Failure:
    error: str
    error_code: str

type Result[T] = Success[T] | Failure

@dataclass
class ProcessPaymentResponse:
    result: Result[Payment]

# Usage
response = ProcessPaymentResponse(
    result=Success(value=Payment(id=123, amount=99.99))
)
# or
response = ProcessPaymentResponse(
    result=Failure(error="Insufficient funds", error_code="INSUFFICIENT_FUNDS")
)
```

### Paginated response

```python
@dataclass
class PaginatedResponse[T]:
    items: list[T]
    total: int
    page: int
    per_page: int
    has_next: bool

    @property
    def total_pages(self) -> int:
        return (self.total + self.per_page - 1) // self.per_page

@dataclass
class User:
    id: int
    username: str

@dataclass
class GetUsersResponse:
    users: PaginatedResponse[User]
```

### Audit trail

```python
@dataclass
class AuditInfo:
    created_by: int
    created_at: datetime
    updated_by: int | None = None
    updated_at: datetime | None = None

@dataclass
class CreateDocumentRequest(Request[DocumentResponse]):
    title: str
    content: str
    audit: AuditInfo
```

### Polymorphic requests

```python
from abc import ABC

@dataclass
class BaseNotificationRequest(Request[NotificationResponse], ABC):
    user_id: int
    message: str

@dataclass
class EmailNotificationRequest(BaseNotificationRequest):
    email: str
    subject: str

@dataclass
class SMSNotificationRequest(BaseNotificationRequest):
    phone_number: str

@dataclass
class PushNotificationRequest(BaseNotificationRequest):
    device_token: str
```

A shared base class like `BaseNotificationRequest` is also what makes [selective pipeline behaviors](pipeline-behaviors.md#selective-behaviors) powerful: a single `PipelineBehavior[BaseNotificationRequest]` automatically applies to every request in the hierarchy, without listing each subclass.

```python
from pymediate.pipeline import PipelineBehavior

class NotificationMetricsBehavior(PipelineBehavior[BaseNotificationRequest]):
    """Emits delivery latency and channel counters for any notification request."""

    def __init__(self, metrics):
        self.metrics = metrics

    def __call__(self, request, next):
        start = time.perf_counter()
        response = next()
        self.metrics.histogram(
            "notification.delivery_seconds",
            time.perf_counter() - start,
            tags={"channel": type(request).__name__},
        )
        self.metrics.increment(f"notification.sent.{type(request).__name__}")
        return response
```

Register it once and it covers `EmailNotificationRequest`, `SMSNotificationRequest`, and `PushNotificationRequest` alike — add a new notification channel later and it's covered automatically, with no behavior-side changes.

---

## Next steps

- Learn about [Requests and Responses](requests-responses.md) - Design patterns
- Explore [Handlers](handlers.md) - Processing dataclass requests
- See [Best Practices](../advanced/best-practices.md) - Advanced techniques
- Read [Type Safety](../advanced/type-safety.md) - Ensuring type correctness
