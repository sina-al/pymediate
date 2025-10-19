"""Comprehensive tests for SimpleResolver type safety and edge cases."""

from dataclasses import dataclass

import pytest

from pymediate import Handler, HandlerTypeMismatchError, Mediator, Request, SimpleResolver

# Test type safety validation


@dataclass
class Response1:
    value: int


@dataclass
class Response2:
    text: str


@dataclass
class Request1(Request[Response1]):
    data: str


@dataclass
class Request2(Request[Response2]):
    number: int


class Handler1(Handler[Request1]):
    def __call__(self, request: Request1) -> Response1:
        return Response1(value=len(request.data))


class Handler2(Handler[Request2]):
    def __call__(self, request: Request2) -> Response2:
        return Response2(text=str(request.number))


def test_type_safe_registration():
    """Test that SimpleResolver validates handler types at registration."""
    resolver = SimpleResolver()

    # This should work - correct handler for request type
    handler1 = Handler1()
    resolver.register(Request1, handler1)

    resolved = resolver.resolve(Request1)
    assert resolved is handler1


def test_type_mismatch_detection():
    """Test that SimpleResolver detects handler type mismatches."""
    resolver = SimpleResolver()

    # Try to register Handler1 for Request2 - should fail
    handler1 = Handler1()

    with pytest.raises(HandlerTypeMismatchError):
        resolver.register(Request2, handler1)


def test_multiple_handlers_type_safety():
    """Test type safety with multiple handlers registered."""
    resolver = SimpleResolver()

    handler1 = Handler1()
    handler2 = Handler2()

    resolver.register(Request1, handler1)
    resolver.register(Request2, handler2)

    # Verify correct handlers are resolved
    assert resolver.resolve(Request1) is handler1
    assert resolver.resolve(Request2) is handler2


def test_initial_handlers_dict_validation():
    """Test that handlers passed to __init__ are validated."""
    handler1 = Handler1()

    # This should work
    resolver = SimpleResolver(handlers={Request1: handler1})
    assert resolver.resolve(Request1) is handler1

    # This should fail - wrong handler for request type
    with pytest.raises(HandlerTypeMismatchError):
        SimpleResolver(handlers={Request2: handler1})


# Test with dataclasses


@dataclass
class UserCreatedResponse:
    user_id: int
    username: str


@dataclass
class CreateUserRequest(Request[UserCreatedResponse]):
    username: str
    email: str


class CreateUserHandler(Handler[CreateUserRequest]):
    def __init__(self):
        self.next_id = 1

    def __call__(self, request: CreateUserRequest) -> UserCreatedResponse:
        user_id = self.next_id
        self.next_id += 1
        return UserCreatedResponse(user_id=user_id, username=request.username)


def test_dataclass_with_type_safe_resolver():
    """Test type-safe resolver with dataclass requests and responses."""
    resolver = SimpleResolver()
    handler = CreateUserHandler()

    resolver.register(CreateUserRequest, handler)

    mediator = Mediator(resolver)
    response = mediator.send(CreateUserRequest(username="alice", email="alice@example.com"))

    assert response.user_id == 1
    assert response.username == "alice"


# Test inheritance and complex types


@dataclass
class BaseResponse:
    status: str


@dataclass
class ExtendedResponse(BaseResponse):
    data: dict


@dataclass
class BaseRequest(Request[BaseResponse]):
    action: str


@dataclass
class ExtendedRequest(Request[ExtendedResponse]):
    action: str
    payload: dict


class BaseHandler(Handler[BaseRequest]):
    def __call__(self, request: BaseRequest) -> BaseResponse:
        return BaseResponse(status="ok")


class ExtendedHandler(Handler[ExtendedRequest]):
    def __call__(self, request: ExtendedRequest) -> ExtendedResponse:
        return ExtendedResponse(status="ok", data=request.payload)


def test_inheritance_hierarchy_type_safety():
    """Test type safety with inheritance hierarchies."""
    resolver = SimpleResolver()

    base_handler = BaseHandler()
    extended_handler = ExtendedHandler()

    resolver.register(BaseRequest, base_handler)
    resolver.register(ExtendedRequest, extended_handler)

    assert resolver.resolve(BaseRequest) is base_handler
    assert resolver.resolve(ExtendedRequest) is extended_handler


# Test nested dataclasses


@dataclass
class Address:
    street: str
    city: str


@dataclass
class UserWithAddressResponse:
    user_id: int
    name: str
    address: Address


@dataclass
class RegisterUserRequest(Request[UserWithAddressResponse]):
    name: str
    address: Address


class RegisterUserHandler(Handler[RegisterUserRequest]):
    def __init__(self):
        self.next_id = 1

    def __call__(self, request: RegisterUserRequest) -> UserWithAddressResponse:
        user_id = self.next_id
        self.next_id += 1
        return UserWithAddressResponse(user_id=user_id, name=request.name, address=request.address)


def test_nested_dataclass_with_type_safe_resolver():
    """Test type-safe resolver with nested dataclass structures."""
    resolver = SimpleResolver()
    handler = RegisterUserHandler()

    resolver.register(RegisterUserRequest, handler)

    mediator = Mediator(resolver)
    address = Address(street="123 Main St", city="Springfield")
    response = mediator.send(RegisterUserRequest(name="John", address=address))

    assert response.user_id == 1
    assert response.name == "John"
    assert response.address.street == "123 Main St"


# Test with generic types


@dataclass
class ListResponse:
    items: list[str]


@dataclass
class DictResponse:
    data: dict[str, int]


@dataclass
class ListRequest(Request[ListResponse]):
    query: str


@dataclass
class DictRequest(Request[DictResponse]):
    keys: list[str]


class ListHandler(Handler[ListRequest]):
    def __call__(self, request: ListRequest) -> ListResponse:
        return ListResponse(items=[request.query] * 3)


class DictHandler(Handler[DictRequest]):
    def __call__(self, request: DictRequest) -> DictResponse:
        return DictResponse(data={k: len(k) for k in request.keys})


def test_generic_types_type_safety():
    """Test type safety with generic types like list and dict."""
    resolver = SimpleResolver()

    list_handler = ListHandler()
    dict_handler = DictHandler()

    resolver.register(ListRequest, list_handler)
    resolver.register(DictRequest, dict_handler)

    mediator = Mediator(resolver)

    list_response = mediator.send(ListRequest(query="test"))
    assert list_response.items == ["test", "test", "test"]

    dict_response = mediator.send(DictRequest(keys=["a", "bb", "ccc"]))
    assert dict_response.data == {"a": 1, "bb": 2, "ccc": 3}


# Test optional types


@dataclass
class OptionalResponse:
    value: str | None
    count: int


@dataclass
class OptionalRequest(Request[OptionalResponse]):
    text: str | None


class OptionalHandler(Handler[OptionalRequest]):
    def __call__(self, request: OptionalRequest) -> OptionalResponse:
        if request.text:
            return OptionalResponse(value=request.text.upper(), count=len(request.text))
        return OptionalResponse(value=None, count=0)


def test_optional_types_type_safety():
    """Test type safety with Optional/Union types."""
    resolver = SimpleResolver()
    handler = OptionalHandler()

    resolver.register(OptionalRequest, handler)

    mediator = Mediator(resolver)

    response1 = mediator.send(OptionalRequest(text="hello"))
    assert response1.value == "HELLO"
    assert response1.count == 5

    response2 = mediator.send(OptionalRequest(text=None))
    assert response2.value is None
    assert response2.count == 0


# Test multiple resolvers with same handler types


def test_multiple_resolvers_independence():
    """Test that multiple resolver instances are independent."""
    resolver1 = SimpleResolver()
    resolver2 = SimpleResolver()

    handler1a = Handler1()
    handler1b = Handler1()

    resolver1.register(Request1, handler1a)
    resolver2.register(Request1, handler1b)

    assert resolver1.resolve(Request1) is handler1a
    assert resolver2.resolve(Request1) is handler1b
    assert resolver1.resolve(Request1) is not resolver2.resolve(Request1)


# Test handler replacement


def test_handler_replacement_type_safety():
    """Test that replacing handlers maintains type safety."""
    resolver = SimpleResolver()

    handler1a = Handler1()
    handler1b = Handler1()

    resolver.register(Request1, handler1a)
    assert resolver.resolve(Request1) is handler1a

    # Replace with another correct handler
    resolver.register(Request1, handler1b)
    assert resolver.resolve(Request1) is handler1b

    # Try to replace with wrong handler type
    handler2 = Handler2()
    with pytest.raises(HandlerTypeMismatchError):
        resolver.register(Request1, handler2)


# Test frozen dataclasses


@dataclass(frozen=True)
class FrozenResponse:
    result: str


@dataclass(frozen=True)
class FrozenRequest(Request[FrozenResponse]):
    input_data: str


class FrozenHandler(Handler[FrozenRequest]):
    def __call__(self, request: FrozenRequest) -> FrozenResponse:
        return FrozenResponse(result=request.input_data.upper())


def test_frozen_dataclass_type_safety():
    """Test type safety with frozen dataclasses."""
    resolver = SimpleResolver()
    handler = FrozenHandler()

    resolver.register(FrozenRequest, handler)

    mediator = Mediator(resolver)
    response = mediator.send(FrozenRequest(input_data="test"))

    assert response.result == "TEST"


# Test with complex validation scenarios


@dataclass
class ValidationResponse:
    is_valid: bool
    errors: list[str]


@dataclass
class ValidationRequest(Request[ValidationResponse]):
    email: str
    age: int

    def __post_init__(self):
        """Validate request data."""
        if self.age < 0:
            raise ValueError("Age must be non-negative")
        if "@" not in self.email:
            raise ValueError("Invalid email")


class ValidationHandler(Handler[ValidationRequest]):
    def __call__(self, request: ValidationRequest) -> ValidationResponse:
        errors = []
        if request.age < 18:
            errors.append("Must be 18 or older")
        if not request.email.endswith(".com"):
            errors.append("Only .com emails accepted")

        return ValidationResponse(is_valid=len(errors) == 0, errors=errors)


def test_validation_dataclass_type_safety():
    """Test type safety with dataclasses that have validation."""
    resolver = SimpleResolver()
    handler = ValidationHandler()

    resolver.register(ValidationRequest, handler)

    mediator = Mediator(resolver)

    # Valid request
    response1 = mediator.send(ValidationRequest(email="user@example.com", age=25))
    assert response1.is_valid is True
    assert response1.errors == []

    # Invalid per handler logic
    response2 = mediator.send(ValidationRequest(email="user@example.org", age=16))
    assert response2.is_valid is False
    assert len(response2.errors) == 2

    # Invalid per request validation
    with pytest.raises(ValueError, match="Invalid email"):
        mediator.send(ValidationRequest(email="invalid", age=25))


# Test edge case: handler without explicit request type


def test_resolver_handles_missing_request_type_gracefully():
    """Test that resolver handles handlers without explicit request types."""
    resolver = SimpleResolver()

    # Create a mock handler without proper type metadata
    class UntypedHandler:
        def __call__(self, request):
            return "result"

    # Should be able to register (no validation if _request_type is None)
    handler = UntypedHandler()
    resolver.register(Request1, handler)

    # Should resolve
    resolved = resolver.resolve(Request1)
    assert resolved is handler
