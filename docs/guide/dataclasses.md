# Dataclasses with PyMediate

PyMediate has first-class support for Python dataclasses, making it easy to create type-safe, validated requests and responses with minimal boilerplate.

## Table of Contents

- [Why Dataclasses?](#why-dataclasses)
- [Basic Usage](#basic-usage)
- [Request Dataclasses](#request-dataclasses)
- [Response Dataclasses](#response-dataclasses)
- [Advanced Features](#advanced-features)
- [Validation](#validation)
- [Frozen Dataclasses](#frozen-dataclasses)
- [Nested Dataclasses](#nested-dataclasses)
- [Default Values and Factories](#default-values-and-factories)
- [Dataclass Mixins](#dataclass-mixins)
- [Testing with Dataclasses](#testing-with-dataclasses)
- [Best Practices](#best-practices)
- [Common Patterns](#common-patterns)

## Why Dataclasses?

Dataclasses provide several benefits for PyMediate applications:

1. **Type Safety**: Full mypy/pyright support with type hints
2. **Less Boilerplate**: Auto-generated `__init__`, `__repr__`, `__eq__`
3. **Immutability**: Use `frozen=True` for immutable requests
4. **Validation**: Use `__post_init__` for custom validation
5. **IDE Support**: Better auto-completion and refactoring
6. **Serialization**: Easy JSON/dict conversion

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

Compare to manual class definition:

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

## Basic Usage

### Minimal Example

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

### Type Hints are Required

```python
# ✅ GOOD: Type hints present
@dataclass
class UserRequest(Request[UserResponse]):
    username: str  # Type hint required
    age: int       # Type hint required

# ❌ BAD: Missing type hints
@dataclass
class UserRequest(Request[UserResponse]):
    username       # Error: type hint required
    age           # Error: type hint required
```

## Request Dataclasses

### Simple Request

```python
@dataclass
class GetUserRequest(Request[UserResponse]):
    user_id: int
```

### Request with Multiple Fields

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

### Request with Optional Fields

```python
@dataclass
class UpdateUserRequest(Request[UserResponse]):
    user_id: int
    username: str | None = None
    email: str | None = None
    age: int | None = None
```

### Request with Default Values

```python
@dataclass
class SearchRequest(Request[SearchResponse]):
    query: str
    page: int = 1
    per_page: int = 10
    sort_by: str = "relevance"
```

## Response Dataclasses

### Simple Response

```python
@dataclass
class UserResponse:
    user_id: int
    username: str
```

### Rich Response with Multiple Fields

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

### Response with Optional Data

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

### Response with Status

```python
@dataclass
class OperationResponse:
    success: bool
    message: str
    error_code: str | None = None
    data: dict | None = None
```

## Advanced Features

### Slots for Performance

```python
@dataclass(slots=True)
class HighPerformanceRequest(Request[Response]):
    user_id: int
    action: str
```

**Benefits:**
- Faster attribute access
- Lower memory usage (no `__dict__`)
- Prevents adding attributes after initialization

**Drawback:**
- Can't use with weak references

### Order Comparison

```python
@dataclass(order=True)
class PriorityRequest(Request[Response]):
    priority: int
    task_id: int

# Can now compare requests
req1 = PriorityRequest(priority=1, task_id=1)
req2 = PriorityRequest(priority=2, task_id=2)
assert req1 < req2  # Compares by priority, then task_id
```

### Exclude from Repr

```python
from dataclasses import dataclass, field

@dataclass
class LoginRequest(Request[LoginResponse]):
    username: str
    password: str = field(repr=False)  # Don't print password in logs

print(LoginRequest(username="alice", password="secret123"))
# Output: LoginRequest(username='alice')
```

### Exclude from Comparison

```python
@dataclass
class EventRequest(Request[EventResponse]):
    event_type: str
    data: dict
    timestamp: datetime = field(compare=False)  # Don't compare timestamps

# Two events with different timestamps are still equal if data matches
event1 = EventRequest(event_type="login", data={"user": "alice"}, timestamp=now())
event2 = EventRequest(event_type="login", data={"user": "alice"}, timestamp=later())
assert event1 == event2  # True (timestamp excluded from comparison)
```

## Validation

### Basic Validation with __post_init__

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

### Complex Validation

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

### Data Normalization in __post_init__

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

**Important:** This requires using `field(init=False)` or reassignment after `__init__`:

```python
from dataclasses import dataclass, field

@dataclass
class SearchRequest(Request[SearchResponse]):
    _query: str
    _filters: list[str]

    def __post_init__(self):
        # Workaround: use object.__setattr__ for frozen dataclasses
        object.__setattr__(self, 'query', self._query.strip().lower())
        object.__setattr__(self, 'filters', list(set(self._filters)))

    query: str = field(init=False)
    filters: list[str] = field(init=False)
```

Or simpler with non-frozen:

```python
@dataclass
class SearchRequest(Request[SearchResponse]):
    query: str
    filters: list[str]

    def __post_init__(self):
        self.query = self.query.strip().lower()
        self.filters = list(set(self.filters))
```

## Frozen Dataclasses

Frozen dataclasses are immutable - perfect for requests.

### Basic Frozen Request

```python
@dataclass(frozen=True)
class GetUserRequest(Request[UserResponse]):
    user_id: int

# Cannot modify after creation
req = GetUserRequest(user_id=123)
req.user_id = 456  # ❌ Error: cannot assign to field 'user_id'
```

### Benefits of Frozen

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

### Frozen with Mutable Defaults (Careful!)

```python
from dataclasses import dataclass, field

# ❌ DANGEROUS: Mutable default with frozen
@dataclass(frozen=True)
class FilterRequest(Request[FilterResponse]):
    filters: list[str] = []  # Don't do this!

# ✅ CORRECT: Use default_factory
@dataclass(frozen=True)
class FilterRequest(Request[FilterResponse]):
    filters: list[str] = field(default_factory=list)
```

## Nested Dataclasses

### Simple Nesting

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

### Deep Nesting

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

### Nested Validation

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

## Default Values and Factories

### Simple Defaults

```python
@dataclass
class SearchRequest(Request[SearchResponse]):
    query: str
    page: int = 1
    per_page: int = 10
    sort: str = "relevance"
```

### Default Factory for Mutable Types

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

# ❌ WRONG: Mutable defaults
@dataclass
class BadRequest(Request[Response]):
    tags: list[str] = []  # All instances share same list!
    metadata: dict = {}   # All instances share same dict!
```

### Custom Default Factory

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

## Dataclass Mixins

### Timestamp Mixin

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

### Validation Mixin

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

### Pagination Mixin

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

### Metadata Mixin

```python
@dataclass
class MetadataMixin:
    metadata: dict = field(default_factory=dict)

    def add_metadata(self, key: str, value: Any) -> None:
        self.metadata[key] = value

@dataclass
class TrackableRequest(MetadataMixin, Request[Response]):
    action: str

# Can add metadata dynamically
req = TrackableRequest(action="create")
req.add_metadata("user_agent", "Mozilla/5.0")
req.add_metadata("ip_address", "192.168.1.1")
```

## Testing with Dataclasses

### Easy Test Data Creation

```python
import pytest
from dataclasses import replace

@pytest.fixture
def base_user_request():
    return CreateUserRequest(
        username="testuser",
        email="test@example.com",
        age=25
    )

def test_create_user(base_user_request):
    # Use base request as-is
    handler = CreateUserHandler(database=mock_db)
    response = handler(base_user_request)
    assert response.user_id > 0

def test_create_user_different_age(base_user_request):
    # Create variation with replace
    request = replace(base_user_request, age=30)
    assert request.username == "testuser"  # Unchanged
    assert request.age == 30  # Changed
```

### Parametrized Testing

```python
@pytest.mark.parametrize("username,email,expected_valid", [
    ("alice", "alice@example.com", True),
    ("bob", "bob@test.com", True),
    ("", "test@example.com", False),  # Empty username
    ("alice", "invalid-email", False),  # Invalid email
    ("ab", "test@example.com", False),  # Username too short
])
def test_user_validation(username, email, expected_valid):
    if expected_valid:
        req = CreateUserRequest(username=username, email=email)
        assert req.username == username
    else:
        with pytest.raises(ValueError):
            CreateUserRequest(username=username, email=email)
```

### Equality Testing

```python
def test_request_equality():
    req1 = GetUserRequest(user_id=123)
    req2 = GetUserRequest(user_id=123)
    req3 = GetUserRequest(user_id=456)

    assert req1 == req2  # Equal values
    assert req1 != req3  # Different values
```

### Serialization Testing

```python
from dataclasses import asdict

def test_request_serialization():
    req = CreateUserRequest(username="alice", email="alice@example.com")

    # Convert to dict
    data = asdict(req)
    assert data == {"username": "alice", "email": "alice@example.com"}

    # Recreate from dict
    req2 = CreateUserRequest(**data)
    assert req == req2
```

## Best Practices

### 1. Always Use Type Hints

```python
# ✅ GOOD: Full type hints
@dataclass
class UserRequest(Request[UserResponse]):
    user_id: int
    username: str
    email: str
    age: int | None = None

# ❌ BAD: Missing type hints
@dataclass
class UserRequest(Request[UserResponse]):
    user_id  # Error
    username  # Error
```

### 2. Use frozen=True for Requests

```python
# ✅ GOOD: Immutable request
@dataclass(frozen=True)
class GetUserRequest(Request[UserResponse]):
    user_id: int

# ❌ QUESTIONABLE: Mutable request
@dataclass
class GetUserRequest(Request[UserResponse]):
    user_id: int
```

### 3. Use default_factory for Mutable Defaults

```python
# ✅ GOOD: default_factory for lists/dicts
@dataclass
class FilterRequest(Request[FilterResponse]):
    tags: list[str] = field(default_factory=list)
    options: dict = field(default_factory=dict)

# ❌ BAD: Mutable default values
@dataclass
class FilterRequest(Request[FilterResponse]):
    tags: list[str] = []  # Shared between all instances!
    options: dict = {}    # Shared between all instances!
```

### 4. Validate in __post_init__

```python
# ✅ GOOD: Validation at creation time
@dataclass
class CreateUserRequest(Request[UserResponse]):
    email: str
    age: int

    def __post_init__(self):
        if "@" not in self.email:
            raise ValueError("Invalid email")
        if self.age < 18:
            raise ValueError("Must be 18+")

# ❌ BAD: Validation in handler
class CreateUserHandler(Handler[CreateUserRequest]):
    def __call__(self, request: CreateUserRequest) -> UserResponse:
        if "@" not in request.email:  # Too late!
            raise ValueError("Invalid email")
```

### 5. Use Descriptive Field Names

```python
# ✅ GOOD: Clear field names
@dataclass
class SearchProductsRequest(Request[SearchResponse]):
    search_query: str
    min_price: float
    max_price: float
    category_id: int
    include_out_of_stock: bool

# ❌ BAD: Unclear abbreviations
@dataclass
class SearchProductsRequest(Request[SearchResponse]):
    q: str  # What does 'q' mean?
    min: float  # Min what?
    max: float  # Max what?
    cat: int  # Category?
    oos: bool  # Out of stock?
```

### 6. Group Related Fields with Nested Dataclasses

```python
# ✅ GOOD: Nested dataclasses
@dataclass
class PriceRange:
    min_price: float
    max_price: float

@dataclass
class SearchRequest(Request[SearchResponse]):
    query: str
    price_range: PriceRange
    category: str

# ❌ QUESTIONABLE: Flat structure
@dataclass
class SearchRequest(Request[SearchResponse]):
    query: str
    min_price: float
    max_price: float
    category: str
```

### 7. Use slots=True for High-Volume Requests

```python
# ✅ GOOD: Slots for frequently created objects
@dataclass(slots=True, frozen=True)
class LogEventRequest(Request[LogResponse]):
    event_type: str
    timestamp: datetime
    data: dict

# Memory usage: ~40% less than regular dataclass
```

## Common Patterns

### Result Type

```python
from typing import Generic, TypeVar

T = TypeVar('T')

@dataclass
class Success[T]:
    value: T

@dataclass
class Failure:
    error: str
    error_code: str

Result = Success[T] | Failure

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

### Paginated Response

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

### Audit Trail

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

### Polymorphic Requests

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

---

## Next Steps

- Learn about [Requests and Responses](requests-responses.md) - Design patterns
- Explore [Handlers](handlers.md) - Processing dataclass requests
- See [Best Practices](../advanced/best-practices.md) - Advanced techniques
- Read [Type Safety](../advanced/type-safety.md) - Ensuring type correctness
