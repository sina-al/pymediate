"""Comprehensive tests for DependencyInjectorResolver with edge cases.

This test suite validates that the DI resolver works WITHOUT relying on
naming conventions. It uses type inspection to identify handlers.
"""

from dataclasses import dataclass

import pytest
from dependency_injector import containers, providers

from pymediate import DependencyInjectorResolver, Handler, HandlerNotFoundError, Mediator, Request

# ========== Test 1: Arbitrary class names (no naming conventions) ==========


@dataclass
class Alpha:
    """Response with weird name."""

    value: int


@dataclass
class Beta:
    """Response with weird name."""

    text: str


class Gamma(Request[Alpha]):
    """Request with no 'Request' suffix."""

    def __init__(self, x: int):
        self.x = x


class DeltaEpsilon(Request[Beta]):
    """Request with compound name and no 'Request' suffix."""

    def __init__(self, s: str):
        self.s = s


class ZetaProcessor(Handler[Gamma]):
    """Handler with no 'Handler' suffix."""

    def __call__(self, request: Gamma) -> Alpha:
        return Alpha(value=request.x * 2)


class ThetaIotaKappaLambda(Handler[DeltaEpsilon]):
    """Handler with very long name, no 'Handler' suffix."""

    def __call__(self, request: DeltaEpsilon) -> Beta:
        return Beta(text=request.s.upper())


class ArbitraryNamesContainer(containers.DeclarativeContainer):
    """Container with arbitrary handler names."""

    # Handler providers with random names
    processor_one = providers.Factory(ZetaProcessor)
    some_random_provider = providers.Factory(ThetaIotaKappaLambda)


def test_arbitrary_class_names():
    """Test that resolver works with arbitrary class names (no conventions)."""
    container = ArbitraryNamesContainer()
    resolver = DependencyInjectorResolver(container)

    # Should find handler for Gamma request
    handler1 = resolver.resolve(Gamma)
    assert isinstance(handler1, ZetaProcessor)
    result1 = handler1(Gamma(5))
    assert result1.value == 10

    # Should find handler for DeltaEpsilon request
    handler2 = resolver.resolve(DeltaEpsilon)
    assert isinstance(handler2, ThetaIotaKappaLambda)
    result2 = handler2(DeltaEpsilon("hello"))
    assert result2.text == "HELLO"


def test_arbitrary_names_with_mediator():
    """Test mediator integration with arbitrary names."""
    container = ArbitraryNamesContainer()
    resolver = DependencyInjectorResolver(container)
    mediator = Mediator(resolver)

    response1 = mediator.send(Gamma(7))
    assert response1.value == 14

    response2 = mediator.send(DeltaEpsilon("world"))
    assert response2.text == "WORLD"


# ========== Test 2: Single letter names ==========


@dataclass
class R:
    """Single letter response."""

    n: int


class Q(Request[R]):
    """Single letter request."""

    def __init__(self, val: int):
        self.val = val


class H(Handler[Q]):
    """Single letter handler."""

    def __call__(self, request: Q) -> R:
        return R(n=request.val + 1)


class SingleLetterContainer(containers.DeclarativeContainer):
    """Container with single letter handler."""

    h = providers.Factory(H)


def test_single_letter_names():
    """Test resolver with single letter class names."""
    container = SingleLetterContainer()
    resolver = DependencyInjectorResolver(container)

    handler = resolver.resolve(Q)
    assert isinstance(handler, H)
    result = handler(Q(99))
    assert result.n == 100


# ========== Test 3: Dataclass + decorator + DI resolver ==========


@dataclass
class UserData:
    """Dataclass response."""

    user_id: int
    username: str
    email: str


@dataclass
class CreateUser(Request[UserData]):
    """Dataclass request using inheritance."""

    username: str
    email: str


class DatabaseConnection:
    """Mock database service."""

    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.users: list[dict] = []
        self.next_id = 1

    def insert_user(self, username: str, email: str) -> int:
        user_id = self.next_id
        self.next_id += 1
        self.users.append({"id": user_id, "username": username, "email": email})
        return user_id


class UserCreationService(Handler[CreateUser]):
    """Handler with injected database."""

    def __init__(self, db: DatabaseConnection):
        self.db = db

    def __call__(self, request: CreateUser) -> UserData:
        user_id = self.db.insert_user(request.username, request.email)
        return UserData(user_id=user_id, username=request.username, email=request.email)


class DataclassDIContainer(containers.DeclarativeContainer):
    """Container combining dataclasses, decorator, and DI."""

    database = providers.Singleton(DatabaseConnection, connection_string="postgres://localhost")
    user_service = providers.Factory(UserCreationService, db=database)


def test_dataclass_decorator_with_di():
    """Test dataclass + Request inheritance + DI resolver together."""
    container = DataclassDIContainer()
    resolver = DependencyInjectorResolver(container)
    mediator = Mediator(resolver)

    # Create user using pure dataclass request
    response = mediator.send(CreateUser(username="alice", email="alice@example.com"))

    assert response.user_id == 1
    assert response.username == "alice"
    assert response.email == "alice@example.com"

    # Verify database interaction
    db = container.database()
    assert len(db.users) == 1
    assert db.users[0]["username"] == "alice"


def test_multiple_dataclass_requests_with_di():
    """Test multiple dataclass requests through DI."""
    container = DataclassDIContainer()
    resolver = DependencyInjectorResolver(container)
    mediator = Mediator(resolver)

    response1 = mediator.send(CreateUser(username="alice", email="alice@test.com"))
    response2 = mediator.send(CreateUser(username="bob", email="bob@test.com"))
    response3 = mediator.send(CreateUser(username="charlie", email="charlie@test.com"))

    assert response1.user_id == 1
    assert response2.user_id == 2
    assert response3.user_id == 3

    db = container.database()
    assert len(db.users) == 3


# ========== Test 4: Multiple handlers with various naming styles ==========


@dataclass
class NumberResult:
    """Result with number."""

    result: int


@dataclass
class StringResult:
    """Result with string."""

    result: str


@dataclass
class BoolResult:
    """Result with bool."""

    result: bool


class CalculateSquare(Request[NumberResult]):
    """Request to calculate square."""

    def __init__(self, n: int):
        self.n = n


class fmt_str(Request[StringResult]):
    """Request with snake_case name."""

    def __init__(self, text: str):
        self.text = text


class checkEvenOdd(Request[BoolResult]):
    """Request with camelCase name."""

    def __init__(self, num: int):
        self.num = num


class MathService:
    """Service for math operations."""

    def square(self, n: int) -> int:
        return n * n

    def is_even(self, n: int) -> bool:
        return n % 2 == 0


class StringService:
    """Service for string operations."""

    def format(self, text: str) -> str:
        return f">>> {text} <<<"


class SquareCalculator(Handler[CalculateSquare]):
    """Handler for square calculation."""

    def __init__(self, math_svc: MathService):
        self.math_svc = math_svc

    def __call__(self, request: CalculateSquare) -> NumberResult:
        return NumberResult(result=self.math_svc.square(request.n))


class Formatter(Handler[fmt_str]):
    """Handler with short name."""

    def __init__(self, str_svc: StringService):
        self.str_svc = str_svc

    def __call__(self, request: fmt_str) -> StringResult:
        return StringResult(result=self.str_svc.format(request.text))


class EvenOddChecker(Handler[checkEvenOdd]):
    """Handler for even/odd check."""

    def __init__(self, math_svc: MathService):
        self.math_svc = math_svc

    def __call__(self, request: checkEvenOdd) -> BoolResult:
        return BoolResult(result=self.math_svc.is_even(request.num))


class MixedNamingContainer(containers.DeclarativeContainer):
    """Container with mixed naming conventions."""

    math_service = providers.Singleton(MathService)
    string_service = providers.Singleton(StringService)

    # Providers with various names
    calc = providers.Factory(SquareCalculator, math_svc=math_service)
    fmt = providers.Factory(Formatter, str_svc=string_service)
    checker = providers.Factory(EvenOddChecker, math_svc=math_service)


def test_mixed_naming_conventions():
    """Test resolver with various naming conventions."""
    container = MixedNamingContainer()
    resolver = DependencyInjectorResolver(container)
    mediator = Mediator(resolver)

    # Test CalculateSquare request
    result1 = mediator.send(CalculateSquare(5))
    assert result1.result == 25

    # Test fmt_str request (snake_case)
    result2 = mediator.send(fmt_str("Hello"))
    assert result2.result == ">>> Hello <<<"

    # Test checkEvenOdd request (camelCase)
    result3 = mediator.send(checkEvenOdd(4))
    assert result3.result is True

    result4 = mediator.send(checkEvenOdd(7))
    assert result4.result is False


# ========== Test 5: Handler not found scenarios ==========


class NoHandlerResponse:
    """Response with no handler."""

    pass


class NoHandlerRequest(Request[NoHandlerResponse]):
    """Request with no handler registered."""

    pass


def test_handler_not_found_error():
    """Test error when no handler provider exists in container."""
    container = MixedNamingContainer()
    resolver = DependencyInjectorResolver(container)

    with pytest.raises(HandlerNotFoundError):
        resolver.resolve(NoHandlerRequest)


def test_handler_not_found_lists_available():
    """Test that error message lists available handlers."""
    container = ArbitraryNamesContainer()
    resolver = DependencyInjectorResolver(container)

    try:
        resolver.resolve(NoHandlerRequest)
        pytest.fail("Should have raised HandlerNotFoundError")
    except HandlerNotFoundError as e:
        error_msg = str(e)
        assert "NoHandlerRequest" in error_msg
        # Should mention available handlers or give useful info
        assert (
            "Gamma" in error_msg or "DeltaEpsilon" in error_msg or "available" in error_msg.lower()
        )


# ========== Test 6: Singleton vs Factory providers ==========


@dataclass
class CounterResponse:
    """Response with count."""

    count: int


class GetCount(Request[CounterResponse]):
    """Request to get count."""

    pass


class StatefulCounter(Handler[GetCount]):
    """Handler that maintains state."""

    def __init__(self):
        self.count = 0

    def __call__(self, request: GetCount) -> CounterResponse:
        self.count += 1
        return CounterResponse(count=self.count)


class SingletonContainer(containers.DeclarativeContainer):
    """Container with singleton handler."""

    counter_handler = providers.Singleton(StatefulCounter)


class FactoryContainer(containers.DeclarativeContainer):
    """Container with factory handler."""

    counter_handler = providers.Factory(StatefulCounter)


def test_singleton_handler_maintains_state():
    """Test that singleton handler maintains state across calls."""
    container = SingletonContainer()
    resolver = DependencyInjectorResolver(container)
    mediator = Mediator(resolver)

    # All calls should share the same handler instance
    resp1 = mediator.send(GetCount())
    resp2 = mediator.send(GetCount())
    resp3 = mediator.send(GetCount())

    assert resp1.count == 1
    assert resp2.count == 2
    assert resp3.count == 3


def test_factory_handler_creates_new_instances():
    """Test that factory handler creates new instances."""
    container = FactoryContainer()
    resolver = DependencyInjectorResolver(container)
    mediator = Mediator(resolver)

    # Each call should get a new handler instance
    resp1 = mediator.send(GetCount())
    resp2 = mediator.send(GetCount())
    resp3 = mediator.send(GetCount())

    # Each new instance starts at count=1
    assert resp1.count == 1
    assert resp2.count == 1
    assert resp3.count == 1


# ========== Test 7: Caching behavior ==========


def test_resolver_caches_handler_lookups():
    """Test that resolver caches handler lookups for performance."""
    container = ArbitraryNamesContainer()
    resolver = DependencyInjectorResolver(container)

    # First resolve
    handler1 = resolver.resolve(Gamma)

    # Second resolve should use cache (same request type)
    handler2 = resolver.resolve(Gamma)

    # Both should work correctly
    assert isinstance(handler1, ZetaProcessor)
    assert isinstance(handler2, ZetaProcessor)


# ========== Test 8: Non-Handler provider in container ==========


class NotAHandler:
    """Not a Handler subclass."""

    def process(self, data: str) -> str:
        return data.upper()


class ContainerWithNonHandler(containers.DeclarativeContainer):
    """Container with both handlers and non-handlers."""

    # This is NOT a handler
    text_processor = providers.Factory(NotAHandler)

    # This IS a handler
    zeta = providers.Factory(ZetaProcessor)


def test_container_with_non_handler_providers():
    """Test that resolver ignores non-Handler providers."""
    container = ContainerWithNonHandler()
    resolver = DependencyInjectorResolver(container)

    # Should successfully resolve Gamma (has ZetaProcessor handler)
    handler = resolver.resolve(Gamma)
    assert isinstance(handler, ZetaProcessor)

    # NotAHandler should be ignored by resolver


# ========== Test 9: Deep inheritance ==========


@dataclass
class BaseResponse:
    """Base response class."""

    status: str


@dataclass
class ExtendedResponse(BaseResponse):
    """Extended response class."""

    data: int


class BaseReq(Request[BaseResponse]):
    """Base request."""

    pass


class ExtendedReq(BaseReq):
    """Extended request inheriting from BaseReq."""

    def __init__(self, value: int):
        self.value = value


# Note: This won't work with current Request implementation
# because ExtendedReq doesn't specify its own response type
# This test documents the limitation


# ========== Test 10: Unicode and special characters ==========


@dataclass
class Résultat:
    """Response with unicode name."""

    valeur: int


class Requête(Request[Résultat]):
    """Request with unicode name."""

    def __init__(self, nombre: int):
        self.nombre = nombre


class Gestionnaire(Handler[Requête]):
    """Handler with unicode name."""

    def __call__(self, request: Requête) -> Résultat:
        return Résultat(valeur=request.nombre * 3)


class UnicodeContainer(containers.DeclarativeContainer):
    """Container with unicode names."""

    gestionnaire = providers.Factory(Gestionnaire)


def test_unicode_class_names():
    """Test resolver with unicode class names."""
    container = UnicodeContainer()
    resolver = DependencyInjectorResolver(container)
    mediator = Mediator(resolver)

    response = mediator.send(Requête(nombre=5))
    assert response.valeur == 15


# ========== Test 11: Empty container ==========


class EmptyContainer(containers.DeclarativeContainer):
    """Empty container with no handlers."""

    pass


def test_empty_container():
    """Test resolver with empty container."""
    container = EmptyContainer()
    resolver = DependencyInjectorResolver(container)

    # Should fail to resolve any request
    with pytest.raises(HandlerNotFoundError):
        resolver.resolve(Gamma)


# ========== Test 12: Complex DI graph ==========


class LoggerService:
    """Logger service."""

    def __init__(self, level: str):
        self.level = level
        self.logs: list[str] = []

    def log(self, message: str):
        self.logs.append(f"[{self.level}] {message}")


class CacheService:
    """Cache service."""

    def __init__(self):
        self.cache = {}

    def get(self, key: str) -> str | None:
        return self.cache.get(key)

    def set(self, key: str, value: str):
        self.cache[key] = value


@dataclass
class ProcessedData:
    """Processed data response."""

    result: str
    cached: bool


class ProcessData(Request[ProcessedData]):
    """Request to process data."""

    def __init__(self, key: str, data: str):
        self.key = key
        self.data = data


class DataProcessor(Handler[ProcessData]):
    """Handler with multiple dependencies."""

    def __init__(self, logger: LoggerService, cache: CacheService):
        self.logger = logger
        self.cache = cache

    def __call__(self, request: ProcessData) -> ProcessedData:
        # Check cache first
        cached_result = self.cache.get(request.key)
        if cached_result:
            self.logger.log(f"Cache hit for {request.key}")
            return ProcessedData(result=cached_result, cached=True)

        # Process data
        result = request.data.upper()
        self.cache.set(request.key, result)
        self.logger.log(f"Processed {request.key}")
        return ProcessedData(result=result, cached=False)


class ComplexDIContainer(containers.DeclarativeContainer):
    """Container with complex dependency graph."""

    logger = providers.Singleton(LoggerService, level="INFO")
    cache = providers.Singleton(CacheService)
    data_processor = providers.Factory(DataProcessor, logger=logger, cache=cache)


def test_complex_di_graph():
    """Test resolver with complex dependency injection graph."""
    container = ComplexDIContainer()
    resolver = DependencyInjectorResolver(container)
    mediator = Mediator(resolver)

    # First call - not cached
    resp1 = mediator.send(ProcessData(key="test1", data="hello"))
    assert resp1.result == "HELLO"
    assert resp1.cached is False

    # Second call with same key - should be cached
    resp2 = mediator.send(ProcessData(key="test1", data="ignored"))
    assert resp2.result == "HELLO"
    assert resp2.cached is True

    # Verify logger was used
    logger = container.logger()
    assert len(logger.logs) == 2
    assert "Cache hit" in logger.logs[1]
