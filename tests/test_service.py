"""Tests for Services, the built-in ServiceProvider.

A ``Services`` is constructed from its instances and resolves them by exact type:
``services[Type]`` returns the instance, ``Type in services`` tests for it, and
``len()`` counts the registered instances. Two instances of one type in a single
construction is an error; ``|`` is how a service gets replaced deliberately.
"""

import threading

import pytest

from pymediate.errors import ServiceAlreadyRegisteredError
from pymediate.service import ServiceNotFoundError, Services


class ServiceA:
    """Simple service for testing."""

    def __init__(self, value: int = 1) -> None:
        self.value = value


class ServiceB:
    """Another simple service for testing."""

    def __init__(self, name: str = "B") -> None:
        self.name = name


class BaseService:
    """Base service class for exact-type resolution testing."""

    def __init__(self, id: int) -> None:
        self.id = id


class ConcreteService(BaseService):
    """Concrete service inheriting from BaseService."""

    def __init__(self, id: int, extra: str = "A") -> None:
        super().__init__(id)
        self.extra = extra


# ==================== Construction ====================


def test_empty_collection() -> None:
    """An empty collection is usable and holds nothing."""
    services = Services()

    assert len(services) == 0
    assert ServiceA not in services
    assert repr(services) == "Services()"


def test_single_instance() -> None:
    """One instance is registered under its concrete type."""
    service = ServiceA(42)
    services = Services(service)

    assert len(services) == 1
    assert services[ServiceA] is service


def test_multiple_different_types() -> None:
    """Instances of different types are all registered."""
    a, b = ServiceA(1), ServiceB("test")
    services = Services(a, b)

    assert len(services) == 2
    assert services[ServiceA] is a
    assert services[ServiceB] is b


def test_duplicate_type_raises() -> None:
    """Two instances of one type in a single construction is a wiring error."""
    with pytest.raises(ServiceAlreadyRegisteredError) as exc_info:
        Services(ServiceA(1), ServiceB("b"), ServiceA(2))

    assert exc_info.value.service_type is ServiceA
    assert "ServiceA" in str(exc_info.value)


def test_same_instance_twice_raises() -> None:
    """The same object passed twice is still a repeated type."""
    singleton = ServiceA(1)

    with pytest.raises(ServiceAlreadyRegisteredError):
        Services(singleton, singleton)


def test_none_raises_value_error() -> None:
    """None cannot be registered as a service instance."""
    with pytest.raises(ValueError, match="Cannot register None"):
        Services(None)

    with pytest.raises(ValueError, match="Cannot register None"):
        Services(ServiceA(1), None)


def test_repr_is_the_constructor_call() -> None:
    """repr names the registered types in registration order."""
    services = Services(ServiceA(1), ServiceB("test"))

    assert repr(services) == "Services(ServiceA, ServiceB)"


def test_iterable_unpacking() -> None:
    """A computed collection of instances registers via unpacking."""
    instances = [ServiceA(1), ServiceB("test")]
    services = Services(*instances)

    assert len(services) == 2
    assert services[ServiceA] is instances[0]


# ==================== Resolution ====================


def test_resolve_returns_the_registered_instance() -> None:
    """Resolution returns the exact object registered, not a copy."""
    service = ServiceA(42)
    services = Services(service)

    resolved = services[ServiceA]

    assert resolved is service
    assert resolved.value == 42


def test_resolve_nonexistent_raises_error() -> None:
    """A miss names the requested type and what is available."""
    services = Services(ServiceA(1))

    with pytest.raises(ServiceNotFoundError) as exc_info:
        services[ServiceB]

    assert exc_info.value.service_type is ServiceB
    assert "ServiceB" in str(exc_info.value)


def test_contains_registered_type() -> None:
    """A registered type is reported as present."""
    services = Services(ServiceA(1))

    assert ServiceA in services


def test_contains_unregistered_type() -> None:
    """An unregistered type is reported as absent."""
    services = Services(ServiceA(1))

    assert ServiceB not in services


def test_resolve_exact_type_no_inheritance() -> None:
    """A base class does not match a registered subclass."""
    services = Services(ConcreteService(1))

    assert services[ConcreteService].id == 1
    with pytest.raises(ServiceNotFoundError):
        services[BaseService]


def test_contains_exact_type_no_inheritance() -> None:
    """Membership is exact-type too - a base class is not present."""
    services = Services(ConcreteService(1))

    assert ConcreteService in services
    assert BaseService not in services


def test_resolve_returns_correct_type() -> None:
    """Each type resolves to an instance of itself."""
    services = Services(ServiceA(42), ServiceB("test"))

    assert isinstance(services[ServiceA], ServiceA)
    assert isinstance(services[ServiceB], ServiceB)


# ==================== Combining with | ====================


def test_or_combines_disjoint_collections() -> None:
    """Combining disjoint collections keeps every service."""
    a, b = ServiceA(1), ServiceB("test")

    combined = Services(a) | Services(b)

    assert len(combined) == 2
    assert combined[ServiceA] is a
    assert combined[ServiceB] is b


def test_or_right_operand_wins() -> None:
    """On a shared type the right operand's instance is the one resolved."""
    original, replacement = ServiceA(1), ServiceA(2)

    combined = Services(original) | Services(replacement)

    assert combined[ServiceA] is replacement
    assert len(combined) == 1


def test_or_leaves_both_operands_unchanged() -> None:
    """Combining is non-mutating - both operands keep their own services."""
    original, replacement = ServiceA(1), ServiceA(2)
    left, right = Services(original), Services(replacement)

    combined = left | right

    assert combined is not left
    assert combined is not right
    assert left[ServiceA] is original
    assert right[ServiceA] is replacement


def test_or_overrides_without_raising() -> None:
    """Unlike the constructor, a shared type is allowed - that is the point."""
    production = Services(ServiceA(1), ServiceB("real"))
    fake = ServiceB("fake")

    for_tests = production | Services(fake)

    assert for_tests[ServiceB] is fake
    assert for_tests[ServiceA].value == 1


def test_or_with_non_services_raises_type_error() -> None:
    """Combining with an unrelated object is a TypeError, via NotImplemented."""
    services = Services(ServiceA(1))

    with pytest.raises(TypeError):
        _ = services | 5  # type: ignore[operator]


def test_or_assignment_rebinds() -> None:
    """`|=` rebinds rather than mutating, since there is no __ior__."""
    accumulated = Services(ServiceA(1))
    before = accumulated

    accumulated |= Services(ServiceB("test"))

    assert accumulated is not before
    assert len(before) == 1
    assert len(accumulated) == 2


# ==================== ServiceNotFoundError ====================


def test_service_not_found_error_attributes() -> None:
    """The error carries the requested type and every available type."""
    services = Services(ServiceA(1), ServiceB("test"))

    with pytest.raises(ServiceNotFoundError) as exc_info:
        services[ConcreteService]

    error = exc_info.value
    assert error.service_type is ConcreteService
    assert set(error.available_types) == {ServiceA, ServiceB}


def test_error_message_clarity() -> None:
    """The message names the requested type and lists what is registered."""
    services = Services(ServiceA(1), ServiceB("test"))

    with pytest.raises(ServiceNotFoundError) as exc_info:
        services[ConcreteService]

    message = str(exc_info.value)
    assert "ConcreteService" in message
    assert "ServiceA" in message
    assert "ServiceB" in message


def test_empty_collection_error_says_none_available() -> None:
    """A miss on an empty collection still produces a readable message."""
    with pytest.raises(ServiceNotFoundError) as exc_info:
        Services()[ServiceA]

    assert "none" in str(exc_info.value)


def test_missing_service_is_catchable_as_key_error() -> None:
    """A miss on the subscript is a KeyError, matching mapping idiom (ADR 0017)."""
    services = Services(ServiceA(1))

    assert issubclass(ServiceNotFoundError, KeyError)
    with pytest.raises(KeyError):
        services[ServiceB]


def test_error_str_is_not_key_error_repr_wrapped() -> None:
    """str() renders the plain multi-line message, not KeyError's repr-wrapped form."""
    services = Services(ServiceA(1))

    with pytest.raises(ServiceNotFoundError) as exc_info:
        services[ServiceB]

    message = str(exc_info.value)
    assert not message.startswith('"')
    assert not message.startswith("'")
    assert "\\n" not in message
    assert message.startswith("No service of type 'ServiceB' is registered.\n")


# ==================== Non-class and primitive services ====================


def test_primitive_types() -> None:
    """Primitives register under their own types, with bool distinct from int."""
    services = Services(42, 3.14, "hello", True, [1, 2, 3], {"key": "value"})

    assert services[int] == 42
    assert services[float] == 3.14
    assert services[str] == "hello"
    assert services[bool] is True
    assert services[list] == [1, 2, 3]
    assert services[dict] == {"key": "value"}
    assert len(services) == 6


def test_duplicate_primitive_type_raises() -> None:
    """Two ints are a repeated type just like two handler instances."""
    with pytest.raises(ServiceAlreadyRegisteredError):
        Services(1, 2)


def test_dynamically_created_types() -> None:
    """Types created at runtime each get their own registration."""
    types = [type(f"Service{i}", (), {}) for i in range(100)]
    services = Services(*(t() for t in types))

    assert len(services) == 100
    for t in types:
        assert isinstance(services[t], t)


# ==================== Thread safety ====================


def test_concurrent_reads() -> None:
    """An immutable collection is safe to read from many threads."""
    types = [type(f"S{i}", (), {}) for i in range(100)]
    services = Services(*(t() for t in types))

    errors: list[Exception] = []

    def reader() -> None:
        try:
            for _ in range(10):
                assert len(services) == 100
        except Exception as e:  # pragma: no cover - only on failure
            errors.append(e)

    threads = [threading.Thread(target=reader) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
