"""Comprehensive dataclass tests covering all edge cases."""

from dataclasses import dataclass, field
from typing import ClassVar, TypeVar

import pytest

from pymediate import Handler, Mediator, Request, SimpleResolver

# ========== Test 1: Basic dataclass inheritance from Request ==========


@dataclass
class BasicResponse:
    """Simple response."""

    value: int


@dataclass
class BasicRequest(Request[BasicResponse]):
    """Dataclass directly inheriting from Request[T]."""

    data: str


class BasicHandler(Handler[BasicRequest]):
    def __call__(self, request: BasicRequest) -> BasicResponse:
        return BasicResponse(value=len(request.data))


def test_basic_dataclass_inheritance():
    """Test that dataclass can inherit from Request[T]."""
    resolver = SimpleResolver()
    resolver.register(BasicRequest, BasicHandler())
    mediator = Mediator(resolver)

    response = mediator.send(BasicRequest(data="hello"))
    assert response.value == 5


# ========== Test 2: Dataclass with default values ==========


@dataclass
class DefaultsResponse:
    result: str
    status: str = "ok"


@dataclass
class DefaultsRequest(Request[DefaultsResponse]):
    name: str
    age: int = 0
    active: bool = True


class DefaultsHandler(Handler[DefaultsRequest]):
    def __call__(self, request: DefaultsRequest) -> DefaultsResponse:
        return DefaultsResponse(
            result=f"{request.name}-{request.age}-{request.active}",
            status="processed",
        )


def test_dataclass_with_defaults():
    """Test dataclass with default values."""
    resolver = SimpleResolver()
    resolver.register(DefaultsRequest, DefaultsHandler())
    mediator = Mediator(resolver)

    # With defaults
    resp1 = mediator.send(DefaultsRequest(name="alice"))
    assert resp1.result == "alice-0-True"
    assert resp1.status == "processed"

    # Override defaults
    resp2 = mediator.send(DefaultsRequest(name="bob", age=25, active=False))
    assert resp2.result == "bob-25-False"


# ========== Test 3: Dataclass with field() ==========


@dataclass
class FieldResponse:
    items: list[str]
    count: int


@dataclass
class FieldRequest(Request[FieldResponse]):
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)
    frozen: bool = field(default=False, init=False)


class FieldHandler(Handler[FieldRequest]):
    def __call__(self, request: FieldRequest) -> FieldResponse:
        all_items = request.tags + list(request.metadata.keys())
        return FieldResponse(items=all_items, count=len(all_items))


def test_dataclass_with_fields():
    """Test dataclass using field() with factories."""
    resolver = SimpleResolver()
    resolver.register(FieldRequest, FieldHandler())
    mediator = Mediator(resolver)

    # Empty defaults
    resp1 = mediator.send(FieldRequest())
    assert resp1.items == []
    assert resp1.count == 0

    # With values
    resp2 = mediator.send(FieldRequest(tags=["a", "b"], metadata={"x": "1"}))
    assert set(resp2.items) == {"a", "b", "x"}
    assert resp2.count == 3


# ========== Test 4: Nested dataclasses ==========


@dataclass
class Address:
    street: str
    city: str


@dataclass
class Person:
    name: str
    address: Address


@dataclass
class NestedResponse:
    person: Person
    formatted: str


@dataclass
class NestedRequest(Request[NestedResponse]):
    name: str
    street: str
    city: str


class NestedHandler(Handler[NestedRequest]):
    def __call__(self, request: NestedRequest) -> NestedResponse:
        address = Address(street=request.street, city=request.city)
        person = Person(name=request.name, address=address)
        formatted = f"{person.name} at {person.address.street}, {person.address.city}"
        return NestedResponse(person=person, formatted=formatted)


def test_nested_dataclasses():
    """Test dataclasses containing other dataclasses."""
    resolver = SimpleResolver()
    resolver.register(NestedRequest, NestedHandler())
    mediator = Mediator(resolver)

    response = mediator.send(NestedRequest(name="Alice", street="123 Main", city="NYC"))
    assert response.person.name == "Alice"
    assert response.person.address.city == "NYC"
    assert "Alice at 123 Main, NYC" in response.formatted


# ========== Test 5: Dataclass inheritance hierarchy ==========


@dataclass
class BaseResponse:
    """Base response class."""

    status: str


@dataclass
class ExtendedResponse(BaseResponse):
    """Extended response with more fields."""

    data: str


@dataclass
class BaseRequest(Request[BaseResponse]):
    """Base request class."""

    id: int


@dataclass
class ExtendedRequest(BaseRequest):
    """Extended request inheriting from another Request."""

    name: str


# Note: This won't work as expected because ExtendedRequest inherits BaseRequest's
# response type. Let's test what happens:


def test_dataclass_inheritance_hierarchy():
    """Test dataclass inheritance from another Request subclass."""
    # ExtendedRequest should inherit BaseResponse from BaseRequest
    from pymediate.registry import _REQUEST_REGISTRY

    # BaseRequest should be registered with BaseResponse
    assert BaseRequest in _REQUEST_REGISTRY
    assert _REQUEST_REGISTRY[BaseRequest] == BaseResponse

    # ExtendedRequest inherits from BaseRequest, so it might not have its own entry
    # unless explicitly set with Request[T]


# ========== Test 6: Dataclass with class variables ==========


@dataclass
class ClassVarResponse:
    value: int


@dataclass
class ClassVarRequest(Request[ClassVarResponse]):
    data: str
    version: ClassVar[str] = "1.0"
    counter: ClassVar[int] = 0


class ClassVarHandler(Handler[ClassVarRequest]):
    def __call__(self, request: ClassVarRequest) -> ClassVarResponse:
        return ClassVarResponse(value=len(request.data))


def test_dataclass_with_class_variables():
    """Test dataclass with ClassVar fields."""
    resolver = SimpleResolver()
    resolver.register(ClassVarRequest, ClassVarHandler())
    mediator = Mediator(resolver)

    # ClassVar should not be part of __init__
    response = mediator.send(ClassVarRequest(data="test"))
    assert response.value == 4
    assert ClassVarRequest.version == "1.0"


# ========== Test 7: Dataclass with post_init ==========


@dataclass
class PostInitResponse:
    computed: str


@dataclass
class PostInitRequest(Request[PostInitResponse]):
    first_name: str
    last_name: str
    full_name: str = field(init=False)

    def __post_init__(self):
        self.full_name = f"{self.first_name} {self.last_name}"


class PostInitHandler(Handler[PostInitRequest]):
    def __call__(self, request: PostInitRequest) -> PostInitResponse:
        return PostInitResponse(computed=request.full_name.upper())


def test_dataclass_with_post_init():
    """Test dataclass with __post_init__ method."""
    resolver = SimpleResolver()
    resolver.register(PostInitRequest, PostInitHandler())
    mediator = Mediator(resolver)

    response = mediator.send(PostInitRequest(first_name="Alice", last_name="Smith"))
    assert response.computed == "ALICE SMITH"


# ========== Test 8: Frozen dataclasses ==========


@dataclass(frozen=True)
class FrozenResponse:
    value: int


@dataclass(frozen=True)
class FrozenRequest(Request[FrozenResponse]):
    data: str
    count: int = 1


class FrozenHandler(Handler[FrozenRequest]):
    def __call__(self, request: FrozenRequest) -> FrozenResponse:
        return FrozenResponse(value=len(request.data) * request.count)


def test_frozen_dataclasses():
    """Test frozen dataclasses (immutable)."""
    resolver = SimpleResolver()
    resolver.register(FrozenRequest, FrozenHandler())
    mediator = Mediator(resolver)

    request = FrozenRequest(data="test", count=3)
    response = mediator.send(request)
    assert response.value == 12

    # Verify immutability
    with pytest.raises(AttributeError):
        request.data = "modified"  # type: ignore


# ========== Test 9: Dataclass with slots ==========


@dataclass(slots=True)
class SlotsResponse:
    result: str


@dataclass(slots=True)
class SlotsRequest(Request[SlotsResponse]):
    value: int
    name: str


class SlotsHandler(Handler[SlotsRequest]):
    def __call__(self, request: SlotsRequest) -> SlotsResponse:
        return SlotsResponse(result=f"{request.name}:{request.value}")


def test_dataclass_with_slots():
    """Test dataclass with __slots__ (Python 3.10+)."""
    resolver = SimpleResolver()
    resolver.register(SlotsRequest, SlotsHandler())
    mediator = Mediator(resolver)

    response = mediator.send(SlotsRequest(value=42, name="test"))
    assert response.result == "test:42"

    # Note: slots don't prevent attributes when inheriting from non-slot class
    # This is expected behavior with Request base class


# ========== Test 10: Dataclass with mixin ==========


class TimestampMixin:
    """Mixin adding timestamp functionality."""

    def get_timestamp(self) -> str:
        return "2025-01-01T00:00:00Z"


@dataclass
class MixinResponse:
    value: int


@dataclass
class MixinRequest(TimestampMixin, Request[MixinResponse]):
    """Request with mixin and Request inheritance."""

    data: str


class MixinHandler(Handler[MixinRequest]):
    def __call__(self, request: MixinRequest) -> MixinResponse:
        timestamp = request.get_timestamp()
        return MixinResponse(value=len(timestamp))


def test_dataclass_with_mixin():
    """Test dataclass with multiple inheritance (mixin + Request)."""
    resolver = SimpleResolver()
    resolver.register(MixinRequest, MixinHandler())
    mediator = Mediator(resolver)

    request = MixinRequest(data="test")
    assert request.get_timestamp() == "2025-01-01T00:00:00Z"

    response = mediator.send(request)
    assert response.value > 0


# ========== Test 11: Multiple mixins ==========


class LoggableMixin:
    def log(self) -> str:
        return "logged"


class ValidatableMixin:
    def validate(self) -> bool:
        return True


@dataclass
class MultiMixinResponse:
    status: str


@dataclass
class MultiMixinRequest(LoggableMixin, ValidatableMixin, Request[MultiMixinResponse]):
    """Request with multiple mixins."""

    data: str


class MultiMixinHandler(Handler[MultiMixinRequest]):
    def __call__(self, request: MultiMixinRequest) -> MultiMixinResponse:
        if request.validate():
            return MultiMixinResponse(status=request.log())
        return MultiMixinResponse(status="invalid")


def test_dataclass_with_multiple_mixins():
    """Test dataclass with multiple mixin classes."""
    resolver = SimpleResolver()
    resolver.register(MultiMixinRequest, MultiMixinHandler())
    mediator = Mediator(resolver)

    response = mediator.send(MultiMixinRequest(data="test"))
    assert response.status == "logged"


# ========== Test 12: Dataclass with complex types ==========


@dataclass
class ComplexResponse:
    items: list[tuple[str, int]]
    mapping: dict[str, list[int]]


@dataclass
class ComplexRequest(Request[ComplexResponse]):
    data: list[tuple[str, int]]
    groups: dict[str, list[int]]


class ComplexHandler(Handler[ComplexRequest]):
    def __call__(self, request: ComplexRequest) -> ComplexResponse:
        return ComplexResponse(items=request.data, mapping=request.groups)


def test_dataclass_with_complex_types():
    """Test dataclass with complex generic types."""
    resolver = SimpleResolver()
    resolver.register(ComplexRequest, ComplexHandler())
    mediator = Mediator(resolver)

    data = [("a", 1), ("b", 2)]
    groups = {"x": [1, 2, 3], "y": [4, 5]}

    response = mediator.send(ComplexRequest(data=data, groups=groups))
    assert response.items == data
    assert response.mapping == groups


# ========== Test 13: Optional and Union types ==========


@dataclass
class OptionalResponse:
    value: str | None
    count: int | None = None


@dataclass
class OptionalRequest(Request[OptionalResponse]):
    name: str | None = None
    age: int | str = 0


class OptionalHandler(Handler[OptionalRequest]):
    def __call__(self, request: OptionalRequest) -> OptionalResponse:
        value = request.name if request.name else "unknown"
        # Only set count if age is non-zero int
        count = int(request.age) if isinstance(request.age, int) and request.age != 0 else None
        return OptionalResponse(value=value, count=count)


def test_dataclass_with_optional_types():
    """Test dataclass with Optional and Union types."""
    resolver = SimpleResolver()
    resolver.register(OptionalRequest, OptionalHandler())
    mediator = Mediator(resolver)

    # None values
    resp1 = mediator.send(OptionalRequest())
    assert resp1.value == "unknown"
    assert resp1.count is None

    # Actual values
    resp2 = mediator.send(OptionalRequest(name="Alice", age=25))
    assert resp2.value == "Alice"
    assert resp2.count == 25


# ========== Test 14: Dataclass with property ==========


@dataclass
class PropertyResponse:
    value: int


@dataclass
class PropertyRequest(Request[PropertyResponse]):
    _data: str = field(repr=False)

    @property
    def data(self) -> str:
        return self._data.upper()


class PropertyHandler(Handler[PropertyRequest]):
    def __call__(self, request: PropertyRequest) -> PropertyResponse:
        return PropertyResponse(value=len(request.data))


def test_dataclass_with_property():
    """Test dataclass with property methods."""
    resolver = SimpleResolver()
    resolver.register(PropertyRequest, PropertyHandler())
    mediator = Mediator(resolver)

    response = mediator.send(PropertyRequest(_data="hello"))
    assert response.value == 5  # len("HELLO")


# ========== Test 15: Dataclass order and comparison ==========


@dataclass(order=True)
class OrderResponse:
    value: int


@dataclass(order=True)
class OrderRequest(Request[OrderResponse]):
    priority: int
    name: str = field(compare=False)


class OrderHandler(Handler[OrderRequest]):
    def __call__(self, request: OrderRequest) -> OrderResponse:
        return OrderResponse(value=request.priority)


def test_dataclass_with_ordering():
    """Test dataclass with order=True for comparison."""
    req1 = OrderRequest(priority=1, name="low")
    req2 = OrderRequest(priority=5, name="high")

    assert req1 < req2
    assert req2 > req1

    resolver = SimpleResolver()
    resolver.register(OrderRequest, OrderHandler())
    mediator = Mediator(resolver)

    response = mediator.send(req1)
    assert response.value == 1


# ========== Test 16: Multiple requests with same response ==========


@dataclass
class SharedResponse:
    result: str


@dataclass
class RequestA(Request[SharedResponse]):
    data_a: str


@dataclass
class RequestB(Request[SharedResponse]):
    data_b: int


class HandlerA(Handler[RequestA]):
    def __call__(self, request: RequestA) -> SharedResponse:
        return SharedResponse(result=f"A:{request.data_a}")


class HandlerB(Handler[RequestB]):
    def __call__(self, request: RequestB) -> SharedResponse:
        return SharedResponse(result=f"B:{request.data_b}")


def test_multiple_requests_same_response():
    """Test multiple request types returning same response type."""
    resolver = SimpleResolver()
    resolver.register(RequestA, HandlerA())
    resolver.register(RequestB, HandlerB())
    mediator = Mediator(resolver)

    resp_a = mediator.send(RequestA(data_a="test"))
    resp_b = mediator.send(RequestB(data_b=42))

    assert resp_a.result == "A:test"
    assert resp_b.result == "B:42"


# ========== Test 17: Dataclass with validation in post_init ==========


@dataclass
class ValidatedResponse:
    value: int


@dataclass
class ValidatedRequest(Request[ValidatedResponse]):
    age: int

    def __post_init__(self):
        if self.age < 0:
            raise ValueError("Age cannot be negative")
        if self.age > 150:
            raise ValueError("Age too high")


class ValidatedHandler(Handler[ValidatedRequest]):
    def __call__(self, request: ValidatedRequest) -> ValidatedResponse:
        return ValidatedResponse(value=request.age)


def test_dataclass_with_validation():
    """Test dataclass with validation in __post_init__."""
    resolver = SimpleResolver()
    resolver.register(ValidatedRequest, ValidatedHandler())
    mediator = Mediator(resolver)

    # Valid age
    response = mediator.send(ValidatedRequest(age=25))
    assert response.value == 25

    # Invalid ages
    with pytest.raises(ValueError, match="cannot be negative"):
        ValidatedRequest(age=-1)

    with pytest.raises(ValueError, match="too high"):
        ValidatedRequest(age=200)


# ========== Test 18: Generic dataclass (if possible) ==========

T = TypeVar("T")


@dataclass
class GenericResponse[T]:
    value: T


# Note: This is tricky with Request[T] because we need concrete types
# Let's test a concrete instantiation:


@dataclass
class IntResponse:
    value: int


@dataclass
class GenericRequest(Request[IntResponse]):
    data: int


class GenericHandler(Handler[GenericRequest]):
    def __call__(self, request: GenericRequest) -> IntResponse:
        return IntResponse(value=request.data * 2)


def test_dataclass_generic_handling():
    """Test dataclass in generic context."""
    resolver = SimpleResolver()
    resolver.register(GenericRequest, GenericHandler())
    mediator = Mediator(resolver)

    response = mediator.send(GenericRequest(data=21))
    assert response.value == 42


# ========== Test 19: Dataclass with init=False fields ==========


@dataclass
class InitFalseResponse:
    computed: str


@dataclass
class InitFalseRequest(Request[InitFalseResponse]):
    base: str
    derived: str = field(init=False)
    count: int = field(init=False)

    def __post_init__(self):
        self.derived = self.base.upper()
        self.count = len(self.base)


class InitFalseHandler(Handler[InitFalseRequest]):
    def __call__(self, request: InitFalseRequest) -> InitFalseResponse:
        return InitFalseResponse(computed=f"{request.derived}:{request.count}")


def test_dataclass_with_init_false():
    """Test dataclass with init=False fields."""
    resolver = SimpleResolver()
    resolver.register(InitFalseRequest, InitFalseHandler())
    mediator = Mediator(resolver)

    response = mediator.send(InitFalseRequest(base="hello"))
    assert response.computed == "HELLO:5"


# ========== Test 20: Empty dataclasses ==========


@dataclass
class EmptyResponse:
    """Response with no fields."""

    pass


@dataclass
class EmptyRequest(Request[EmptyResponse]):
    """Request with no fields."""

    pass


class EmptyHandler(Handler[EmptyRequest]):
    def __call__(self, request: EmptyRequest) -> EmptyResponse:
        return EmptyResponse()


def test_empty_dataclasses():
    """Test dataclasses with no fields."""
    resolver = SimpleResolver()
    resolver.register(EmptyRequest, EmptyHandler())
    mediator = Mediator(resolver)

    response = mediator.send(EmptyRequest())
    assert isinstance(response, EmptyResponse)


# ========== DI INTEGRATION TESTS ==========


def test_dataclass_with_di_basic():
    """Test basic dataclass with dependency injection."""
    from dependency_injector import containers, providers

    from pymediate import DependencyInjectorResolver

    @dataclass
    class DIResponse:
        user_id: int
        username: str

    @dataclass
    class DIRequest(Request[DIResponse]):
        username: str
        email: str

    class Database:
        def __init__(self):
            self.next_id = 1

        def insert_user(self, username: str, email: str) -> int:
            user_id = self.next_id
            self.next_id += 1
            return user_id

    class DIHandler(Handler[DIRequest]):
        def __init__(self, database: Database):
            self.database = database

        def __call__(self, request: DIRequest) -> DIResponse:
            user_id = self.database.insert_user(request.username, request.email)
            return DIResponse(user_id=user_id, username=request.username)

    class DIContainer(containers.DeclarativeContainer):
        database = providers.Singleton(Database)
        user_handler = providers.Factory(DIHandler, database=database)

    container = DIContainer()
    resolver = DependencyInjectorResolver(container)
    mediator = Mediator(resolver)

    response = mediator.send(DIRequest(username="alice", email="alice@example.com"))
    assert response.user_id == 1
    assert response.username == "alice"


def test_dataclass_with_di_frozen():
    """Test frozen dataclass with DI."""
    from dependency_injector import containers, providers

    from pymediate import DependencyInjectorResolver

    @dataclass(frozen=True)
    class FrozenDIResponse:
        value: int

    @dataclass(frozen=True)
    class FrozenDIRequest(Request[FrozenDIResponse]):
        data: str

    class Service:
        def process(self, data: str) -> int:
            return len(data) * 2

    class FrozenDIHandler(Handler[FrozenDIRequest]):
        def __init__(self, service: Service):
            self.service = service

        def __call__(self, request: FrozenDIRequest) -> FrozenDIResponse:
            return FrozenDIResponse(value=self.service.process(request.data))

    class FrozenDIContainer(containers.DeclarativeContainer):
        service = providers.Singleton(Service)
        handler = providers.Factory(FrozenDIHandler, service=service)

    container = FrozenDIContainer()
    resolver = DependencyInjectorResolver(container)
    mediator = Mediator(resolver)

    response = mediator.send(FrozenDIRequest(data="test"))
    assert response.value == 8


def test_dataclass_with_di_nested():
    """Test nested dataclasses with DI."""
    from dependency_injector import containers, providers

    from pymediate import DependencyInjectorResolver

    @dataclass
    class NestedDIAddress:
        street: str
        city: str

    @dataclass
    class NestedDIResponse:
        id: int
        address: NestedDIAddress

    @dataclass
    class NestedDIRequest(Request[NestedDIResponse]):
        street: str
        city: str

    class AddressService:
        def __init__(self):
            self.next_id = 100

        def create_address(self, street: str, city: str) -> tuple[int, NestedDIAddress]:
            addr = NestedDIAddress(street=street, city=city)
            addr_id = self.next_id
            self.next_id += 1
            return addr_id, addr

    class NestedDIHandler(Handler[NestedDIRequest]):
        def __init__(self, address_service: AddressService):
            self.address_service = address_service

        def __call__(self, request: NestedDIRequest) -> NestedDIResponse:
            addr_id, address = self.address_service.create_address(request.street, request.city)
            return NestedDIResponse(id=addr_id, address=address)

    class NestedDIContainer(containers.DeclarativeContainer):
        address_service = providers.Singleton(AddressService)
        handler = providers.Factory(NestedDIHandler, address_service=address_service)

    container = NestedDIContainer()
    resolver = DependencyInjectorResolver(container)
    mediator = Mediator(resolver)

    response = mediator.send(NestedDIRequest(street="123 Main", city="NYC"))
    assert response.id == 100
    assert response.address.city == "NYC"


def test_dataclass_with_di_multiple_dependencies():
    """Test dataclass handler with multiple DI dependencies."""
    from dependency_injector import containers, providers

    from pymediate import DependencyInjectorResolver

    @dataclass
    class MultiDepResponse:
        cached: bool
        logged: bool
        result: str

    @dataclass
    class MultiDepRequest(Request[MultiDepResponse]):
        key: str
        value: str

    class CacheService:
        def __init__(self):
            self.cache: dict[str, str] = {}

        def set(self, key: str, value: str) -> None:
            self.cache[key] = value

    class LoggerService:
        def __init__(self):
            self.logs: list[str] = []

        def log(self, message: str) -> None:
            self.logs.append(message)

    class MultiDepHandler(Handler[MultiDepRequest]):
        def __init__(self, cache: CacheService, logger: LoggerService):
            self.cache = cache
            self.logger = logger

        def __call__(self, request: MultiDepRequest) -> MultiDepResponse:
            self.cache.set(request.key, request.value)
            self.logger.log(f"Set {request.key}={request.value}")
            return MultiDepResponse(
                cached=request.key in self.cache.cache,
                logged=len(self.logger.logs) > 0,
                result=f"{request.key}:{request.value}",
            )

    class MultiDepContainer(containers.DeclarativeContainer):
        cache = providers.Singleton(CacheService)
        logger = providers.Singleton(LoggerService)
        handler = providers.Factory(MultiDepHandler, cache=cache, logger=logger)

    container = MultiDepContainer()
    resolver = DependencyInjectorResolver(container)
    mediator = Mediator(resolver)

    response = mediator.send(MultiDepRequest(key="test", value="data"))
    assert response.cached is True
    assert response.logged is True
    assert response.result == "test:data"


def test_dataclass_with_di_mixin():
    """Test dataclass with mixin and DI."""
    from dependency_injector import containers, providers

    from pymediate import DependencyInjectorResolver

    class AuditMixin:
        def audit_log(self) -> str:
            return "audited"

    @dataclass
    class MixinDIResponse:
        status: str

    @dataclass
    class MixinDIRequest(AuditMixin, Request[MixinDIResponse]):
        action: str

    class AuditService:
        def record(self, message: str) -> bool:
            return True

    class MixinDIHandler(Handler[MixinDIRequest]):
        def __init__(self, audit_service: AuditService):
            self.audit_service = audit_service

        def __call__(self, request: MixinDIRequest) -> MixinDIResponse:
            audit_msg = request.audit_log()
            self.audit_service.record(audit_msg)
            return MixinDIResponse(status=f"{request.action}:{audit_msg}")

    class MixinDIContainer(containers.DeclarativeContainer):
        audit = providers.Singleton(AuditService)
        handler = providers.Factory(MixinDIHandler, audit_service=audit)

    container = MixinDIContainer()
    resolver = DependencyInjectorResolver(container)
    mediator = Mediator(resolver)

    response = mediator.send(MixinDIRequest(action="create"))
    assert response.status == "create:audited"
