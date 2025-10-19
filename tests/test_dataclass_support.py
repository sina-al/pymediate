"""Tests for dataclass-based requests and responses.

This module demonstrates best practices for using dataclasses with PyMediate,
providing type safety and better IDE support.
"""

from dataclasses import dataclass
from datetime import datetime

from pymediate import Handler, Mediator, Request, SimpleResolver

# Test using Request inheritance with pure dataclasses (recommended pattern)


@dataclass
class PureUserResponse:
    """Pure dataclass response - no inheritance needed."""

    user_id: int
    username: str
    email: str


@dataclass
class PureUserRequest(Request[PureUserResponse]):
    """Pure dataclass request inheriting from Request.

    Uses Request[ResponseType] to specify response type.
    This is the recommended pattern for dataclasses!
    """

    username: str
    email: str


class PureUserHandler(Handler[PureUserRequest]):
    def __call__(self, req: PureUserRequest) -> PureUserResponse:
        return PureUserResponse(user_id=1, username=req.username, email=req.email)


def test_pure_dataclass_with_decorator():
    """Test using Request inheritance with pure dataclasses (RECOMMENDED PATTERN).

    This is the cleanest way to use dataclasses with PyMediate:
    - Both request and response are pure dataclasses
    - Request inherits from Request[ResponseType]
    - Full type safety
    - IDE autocomplete support
    """
    handler = PureUserHandler()
    resolver = SimpleResolver()
    resolver.register(PureUserRequest, handler)
    mediator = Mediator(resolver)

    req = PureUserRequest(username="alice", email="alice@example.com")
    response = mediator.send(req)

    # All fields are properly typed
    assert response.user_id == 1
    assert response.username == "alice"
    assert response.email == "alice@example.com"

    # Both are pure dataclasses - no wrapping!
    assert isinstance(response, PureUserResponse)
    assert isinstance(req, PureUserRequest)


# Test using simple dataclasses with inheritance (also works)


@dataclass
class SimpleResponse:
    """Simple response with basic types."""

    message: str
    status_code: int


class SimpleRequest(Request[SimpleResponse]):
    """Simple request with string data."""

    def __init__(self, text: str):
        self.text = text


class SimpleHandler(Handler[SimpleRequest]):
    def __call__(self, request: SimpleRequest) -> SimpleResponse:
        return SimpleResponse(message=f"Processed: {request.text}", status_code=200)


def test_simple_dataclass_response():
    """Test handler with simple dataclass response."""
    handler = SimpleHandler()
    resolver = SimpleResolver()
    resolver.register(SimpleRequest, handler)
    mediator = Mediator(resolver)

    request = SimpleRequest("hello world")
    response = mediator.send(request)

    assert isinstance(response, SimpleResponse)
    assert response.message == "Processed: hello world"
    assert response.status_code == 200


# Test using dataclass for both request and response


@dataclass
class UserResponse:
    """User data response."""

    user_id: int
    username: str
    email: str
    created_at: datetime
    is_active: bool = True


@dataclass
class CreateUserRequest:
    """Request to create a new user."""

    username: str
    email: str
    password: str


# Need to wrap dataclass request in Request metaclass
class CreateUserRequestWrapped(Request[UserResponse]):
    """Wrapped version of CreateUserRequest for metaclass magic."""

    def __init__(self, username: str, email: str, password: str):
        self.username = username
        self.email = email
        self.password = password


class CreateUserHandler(Handler[CreateUserRequestWrapped]):
    def __init__(self):
        self.next_id = 1

    def __call__(self, request: CreateUserRequestWrapped) -> UserResponse:
        user = UserResponse(
            user_id=self.next_id,
            username=request.username,
            email=request.email,
            created_at=datetime.now(),
            is_active=True,
        )
        self.next_id += 1
        return user


def test_dataclass_user_creation():
    """Test creating a user with dataclass response."""
    handler = CreateUserHandler()
    resolver = SimpleResolver()
    resolver.register(CreateUserRequestWrapped, handler)
    mediator = Mediator(resolver)

    request = CreateUserRequestWrapped(
        username="alice", email="alice@example.com", password="secret123"
    )
    response = mediator.send(request)

    assert isinstance(response, UserResponse)
    assert response.user_id == 1
    assert response.username == "alice"
    assert response.email == "alice@example.com"
    assert response.is_active is True
    assert isinstance(response.created_at, datetime)


def test_multiple_users_with_dataclass():
    """Test creating multiple users maintains state."""
    handler = CreateUserHandler()
    resolver = SimpleResolver()
    resolver.register(CreateUserRequestWrapped, handler)
    mediator = Mediator(resolver)

    # Create first user
    user1 = mediator.send(CreateUserRequestWrapped("alice", "alice@example.com", "pass1"))
    assert user1.user_id == 1
    assert user1.username == "alice"

    # Create second user
    user2 = mediator.send(CreateUserRequestWrapped("bob", "bob@example.com", "pass2"))
    assert user2.user_id == 2
    assert user2.username == "bob"

    # Verify they're different instances
    assert user1.user_id != user2.user_id


# Test with optional fields and complex types


@dataclass
class OrderResponse:
    """Order response with optional fields."""

    order_id: int
    total_amount: float
    items_count: int
    discount: float | None = None
    promo_code: str | None = None
    shipping_address: str | None = None


@dataclass
class OrderItem:
    """Individual order item."""

    product_id: int
    name: str
    price: float
    quantity: int


class CreateOrderRequest(Request[OrderResponse]):
    """Request to create an order."""

    def __init__(
        self,
        items: list[OrderItem],
        promo_code: str | None = None,
        shipping_address: str | None = None,
    ):
        self.items = items
        self.promo_code = promo_code
        self.shipping_address = shipping_address


class CreateOrderHandler(Handler[CreateOrderRequest]):
    def __init__(self):
        self.next_order_id = 1000

    def __call__(self, request: CreateOrderRequest) -> OrderResponse:
        total = sum(item.price * item.quantity for item in request.items)
        discount = None

        if request.promo_code == "SAVE10":
            discount = total * 0.1
            total -= discount

        order = OrderResponse(
            order_id=self.next_order_id,
            total_amount=total,
            items_count=len(request.items),
            discount=discount,
            promo_code=request.promo_code,
            shipping_address=request.shipping_address,
        )
        self.next_order_id += 1
        return order


def test_dataclass_order_without_promo():
    """Test creating an order without promo code."""
    handler = CreateOrderHandler()
    resolver = SimpleResolver()
    resolver.register(CreateOrderRequest, handler)
    mediator = Mediator(resolver)

    items = [
        OrderItem(product_id=1, name="Widget", price=10.0, quantity=2),
        OrderItem(product_id=2, name="Gadget", price=15.0, quantity=1),
    ]
    request = CreateOrderRequest(items=items)
    response = mediator.send(request)

    assert response.order_id == 1000
    assert response.total_amount == 35.0  # (10*2) + (15*1)
    assert response.items_count == 2
    assert response.discount is None
    assert response.promo_code is None


def test_dataclass_order_with_promo():
    """Test creating an order with promo code and address."""
    handler = CreateOrderHandler()
    resolver = SimpleResolver()
    resolver.register(CreateOrderRequest, handler)
    mediator = Mediator(resolver)

    items = [
        OrderItem(product_id=1, name="Widget", price=100.0, quantity=1),
    ]
    request = CreateOrderRequest(items=items, promo_code="SAVE10", shipping_address="123 Main St")
    response = mediator.send(request)

    assert response.order_id == 1000
    assert response.total_amount == 90.0  # 100 - 10% discount
    assert response.discount == 10.0
    assert response.promo_code == "SAVE10"
    assert response.shipping_address == "123 Main St"


# Test with nested dataclasses


@dataclass
class Address:
    """Address data."""

    street: str
    city: str
    country: str
    zip_code: str


@dataclass
class CompleteUserResponse:
    """User with nested address."""

    user_id: int
    name: str
    email: str
    address: Address
    is_premium: bool = False


class RegisterUserRequest(Request[CompleteUserResponse]):
    """Request to register a user with address."""

    def __init__(self, name: str, email: str, address: Address):
        self.name = name
        self.email = email
        self.address = address


class RegisterUserHandler(Handler[RegisterUserRequest]):
    def __init__(self):
        self.next_id = 1

    def __call__(self, request: RegisterUserRequest) -> CompleteUserResponse:
        user = CompleteUserResponse(
            user_id=self.next_id,
            name=request.name,
            email=request.email,
            address=request.address,
            is_premium=False,
        )
        self.next_id += 1
        return user


def test_nested_dataclass():
    """Test with nested dataclass structures."""
    handler = RegisterUserHandler()
    resolver = SimpleResolver()
    resolver.register(RegisterUserRequest, handler)
    mediator = Mediator(resolver)

    address = Address(street="123 Main St", city="Springfield", country="USA", zip_code="12345")
    request = RegisterUserRequest(name="John Doe", email="john@example.com", address=address)
    response = mediator.send(request)

    assert response.user_id == 1
    assert response.name == "John Doe"
    assert response.address.street == "123 Main St"
    assert response.address.city == "Springfield"
    assert response.is_premium is False


def test_dataclass_field_access():
    """Test that dataclass fields are properly accessible with type hints."""
    handler = RegisterUserHandler()
    resolver = SimpleResolver()
    resolver.register(RegisterUserRequest, handler)
    mediator = Mediator(resolver)

    address = Address(street="456 Oak Ave", city="Portland", country="USA", zip_code="97201")
    request = RegisterUserRequest(name="Jane Smith", email="jane@example.com", address=address)
    response = mediator.send(request)

    # These should not raise Pylance errors due to proper typing
    assert response.user_id == 1
    assert response.name == "Jane Smith"
    assert response.email == "jane@example.com"
    assert response.address.city == "Portland"
    assert response.address.zip_code == "97201"
