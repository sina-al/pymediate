"""Tests for Services and the built-in ServiceProvider.

The provider resolves by exact type: ``get()`` returns the first-registered instance
of exactly the requested type, ``has()`` tests for it, ``get_all_types()`` lists the
registered types, and ``len()`` counts every registration.
"""

import threading

import pytest

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


# ==================== Services Tests ====================


def test_collection_initialization() -> None:
    """Test that Services initializes empty."""
    services = Services()

    assert len(services) == 0
    assert repr(services) == "Services(services={}, total=0)"


def test_add_single_service() -> None:
    """Test adding a single service instance."""
    services = Services()
    result = services.add(ServiceA(42))

    assert result is services  # Method chaining
    assert len(services) == 1


def test_add_multiple_different_services() -> None:
    """Test adding multiple different service types."""
    services = Services()
    services.add(ServiceA(1))
    services.add(ServiceB("test"))

    assert len(services) == 2


def test_add_multiple_same_type() -> None:
    """Test adding multiple instances of the same type."""
    services = Services()
    services.add(ServiceA(1))
    services.add(ServiceA(2))
    services.add(ServiceA(3))

    assert len(services) == 3


def test_add_none_raises_error() -> None:
    """Test that adding None raises ValueError."""
    services = Services()

    with pytest.raises(ValueError, match="Cannot register None"):
        services.add(None)


def test_add_method_chaining() -> None:
    """Test that add() supports method chaining."""
    services = Services()
    result = services.add(ServiceA(1)).add(ServiceB("test"))

    assert result is services
    assert len(services) == 2


def test_collection_clear() -> None:
    """Test clearing the collection."""
    services = Services()
    services.add(ServiceA(1))
    services.add(ServiceB("test"))

    assert len(services) == 2

    services.clear()

    assert len(services) == 0


def test_collection_repr() -> None:
    """Test string representation of collection."""
    services = Services()
    services.add(ServiceA(1))
    services.add(ServiceA(2))
    services.add(ServiceB("test"))

    repr_str = repr(services)

    assert "Services" in repr_str
    assert "total=3" in repr_str
    assert "ServiceA" in repr_str
    assert "ServiceB" in repr_str


# ==================== ServiceProvider Tests ====================


def test_provider() -> None:
    """Test building a provider from a collection."""
    services = Services()
    services.add(ServiceA(42))

    provider = services.provider()

    assert hasattr(provider, "get")
    assert hasattr(provider, "has")
    assert hasattr(provider, "get_all_types")
    assert len(provider) == 1


def test_provider_immutability() -> None:
    """Test that provider is immutable and not affected by collection changes."""
    services = Services()
    services.add(ServiceA(1))

    provider = services.provider()

    # Modify collection after creating provider
    services.add(ServiceB("test"))

    # Provider should not reflect the change
    assert len(provider) == 1
    assert not provider.has(ServiceB)


def test_resolve_single_service() -> None:
    """Test resolving a single registered service."""
    services = Services()
    service_a = ServiceA(42)
    services.add(service_a)

    provider = services.provider()
    resolved = provider.get(ServiceA)

    assert resolved is service_a
    assert resolved.value == 42


def test_resolve_first_of_multiple() -> None:
    """Test that get() returns the first-registered instance of an exact type."""
    services = Services()
    first = ServiceA(1)
    services.add(first)
    services.add(ServiceA(2))
    services.add(ServiceA(3))

    provider = services.provider()

    assert provider.get(ServiceA) is first
    assert provider.get(ServiceA).value == 1


def test_resolve_nonexistent_raises_error() -> None:
    """Test that resolving an unregistered type raises ServiceNotFoundError."""
    services = Services()
    services.add(ServiceA(1))

    provider = services.provider()

    with pytest.raises(ServiceNotFoundError) as exc_info:
        provider.get(ServiceB)

    assert exc_info.value.service_type == ServiceB
    assert ServiceA in exc_info.value.available_types
    assert "ServiceB" in str(exc_info.value)


def test_has_registered_type() -> None:
    """Test has() returns True for a registered type."""
    services = Services()
    services.add(ServiceA(1))

    provider = services.provider()

    assert provider.has(ServiceA) is True


def test_has_unregistered_type() -> None:
    """Test has() returns False for an unregistered type."""
    services = Services()
    services.add(ServiceA(1))

    provider = services.provider()

    assert provider.has(ServiceB) is False


def test_get_all_types() -> None:
    """Test get_all_types() returns every registered exact type."""
    services = Services()
    services.add(ServiceA(1))
    services.add(ServiceB("test"))
    services.add(ServiceA(2))  # Second instance of an existing type

    provider = services.provider()
    all_types = provider.get_all_types()

    assert set(all_types) == {ServiceA, ServiceB}


def test_provider_len() -> None:
    """Test len() on provider returns the total instance count."""
    services = Services()
    services.add(ServiceA(1))
    services.add(ServiceA(2))
    services.add(ServiceB("test"))

    provider = services.provider()

    assert len(provider) == 3


def test_provider_repr() -> None:
    """Test string representation of provider."""
    services = Services()
    services.add(ServiceA(1))
    services.add(ServiceA(2))
    services.add(ServiceB("test"))

    provider = services.provider()
    repr_str = repr(provider)

    assert "ServiceProvider" in repr_str
    assert "total=3" in repr_str


# ==================== Exact-Type Resolution ====================


def test_resolve_exact_type_no_inheritance() -> None:
    """Test that get() matches the exact type only, not a registered subclass."""
    services = Services()
    services.add(ConcreteService(1))

    provider = services.provider()

    # get() looks for the exact type only, so a base-class request misses a subclass.
    with pytest.raises(ServiceNotFoundError):
        provider.get(BaseService)

    assert provider.get(ConcreteService).id == 1


def test_has_exact_type_no_inheritance() -> None:
    """Test that has() checks the exact type only, not subclasses."""
    services = Services()
    services.add(ConcreteService(1))

    provider = services.provider()

    assert provider.has(ConcreteService) is True
    assert provider.has(BaseService) is False


# ==================== Edge Cases and Error Handling ====================


def test_empty_collection_provider() -> None:
    """Test creating a provider from an empty collection."""
    services = Services()
    provider = services.provider()

    assert len(provider) == 0
    assert provider.get_all_types() == ()
    assert not provider.has(ServiceA)


def test_multiple_providers_from_same_collection() -> None:
    """Test that multiple providers can be created from the same collection."""
    services = Services()
    services.add(ServiceA(1))

    provider1 = services.provider()
    provider2 = services.provider()

    assert provider1.get(ServiceA).value == 1
    assert provider2.get(ServiceA).value == 1
    assert provider1 is not provider2


def test_provider_snapshot_isolation() -> None:
    """Test that providers are true snapshots isolated from the collection."""
    services = Services()
    services.add(ServiceA(1))

    provider1 = services.provider()

    services.add(ServiceA(2))
    services.add(ServiceB("test"))

    provider2 = services.provider()

    assert len(provider1) == 1
    assert set(provider1.get_all_types()) == {ServiceA}

    assert len(provider2) == 3
    assert set(provider2.get_all_types()) == {ServiceA, ServiceB}


def test_clear_does_not_affect_existing_providers() -> None:
    """Test that clearing the collection doesn't affect existing providers."""
    services = Services()
    services.add(ServiceA(1))

    provider = services.provider()

    services.clear()

    assert len(provider) == 1
    assert provider.has(ServiceA)


def test_service_not_found_error_attributes() -> None:
    """Test ServiceNotFoundError carries the requested and available types."""
    services = Services()
    services.add(ServiceA(1))
    services.add(ServiceB("test"))

    provider = services.provider()

    with pytest.raises(ServiceNotFoundError) as exc_info:
        provider.get(ConcreteService)

    error = exc_info.value
    assert error.service_type == ConcreteService
    assert set(error.available_types) == {ServiceA, ServiceB}


def test_error_message_clarity() -> None:
    """Test that error messages name the requested and available types."""
    services = Services()
    services.add(ServiceA(1))
    services.add(ServiceB("test"))

    provider = services.provider()

    with pytest.raises(ServiceNotFoundError) as exc_info:
        provider.get(ConcreteService)

    message = str(exc_info.value)
    assert "ConcreteService" in message
    assert "ServiceA" in message
    assert "ServiceB" in message


def test_type_with_no_instances() -> None:
    """Test exact-type checks when no instances exist for that type."""
    services = Services()
    services.add(ServiceA(1))

    provider = services.provider()

    assert not provider.has(ServiceB)

    with pytest.raises(ServiceNotFoundError):
        provider.get(ServiceB)


def test_none_type_handling() -> None:
    """Test that None is rejected at registration."""
    services = Services()

    with pytest.raises(ValueError, match="Cannot register None"):
        services.add(None)


def test_multiple_providers_independence() -> None:
    """Test that providers built at different times are independent snapshots."""
    services = Services()
    services.add(ServiceA(1))

    provider1 = services.provider()

    services.add(ServiceA(2))

    provider2 = services.provider()

    assert len(provider1) == 1
    assert len(provider2) == 2
    assert provider1 is not provider2


def test_clear_and_rebuild() -> None:
    """Test clearing the collection and building a new provider."""
    services = Services()
    services.add(ServiceA(1))

    provider1 = services.provider()

    services.clear()
    services.add(ServiceB("test"))

    provider2 = services.provider()

    assert provider1.has(ServiceA)
    assert not provider1.has(ServiceB)

    assert not provider2.has(ServiceA)
    assert provider2.has(ServiceB)


# ==================== Type Safety ====================


def test_resolve_returns_correct_type() -> None:
    """Test that get() returns a correctly typed instance."""
    services = Services()
    services.add(ServiceA(42))

    provider = services.provider()
    resolved: ServiceA = provider.get(ServiceA)

    assert isinstance(resolved, ServiceA)
    assert resolved.value == 42


# ==================== Primitives ====================


def test_primitive_types() -> None:
    """Test registering and resolving primitive types by exact type."""
    services = Services()
    services.add(42)
    services.add(3.14)
    services.add("hello")
    services.add(True)
    services.add([1, 2, 3])
    services.add({"key": "value"})

    provider = services.provider()

    assert provider.get(int) == 42
    assert provider.get(float) == 3.14
    assert provider.get(str) == "hello"
    assert provider.get(bool) is True  # bool is a distinct exact type from int
    assert provider.get(list) == [1, 2, 3]
    assert provider.get(dict) == {"key": "value"}


def test_multiple_primitives_same_type() -> None:
    """Test multiple instances of the same primitive type."""
    services = Services()
    services.add(1)
    services.add(2)
    services.add(3)

    provider = services.provider()

    assert provider.get(int) == 1  # First registered
    assert len(provider) == 3


# ==================== Same Instance Multiple Registrations ====================


def test_same_instance_registered_twice() -> None:
    """Test registering the same instance multiple times counts each registration."""
    services = Services()
    singleton = ServiceA(42)

    services.add(singleton)
    services.add(singleton)
    services.add(singleton)

    provider = services.provider()

    assert len(provider) == 3
    assert provider.get(ServiceA) is singleton


def test_same_instance_identity_preserved() -> None:
    """Test that instance identity is preserved through resolution."""
    services = Services()
    singleton = ServiceA(42)

    services.add(singleton)
    provider = services.provider()

    assert provider.get(ServiceA) is singleton  # Same object, not a copy


# ==================== Scale ====================


def test_large_number_of_services() -> None:
    """Test handling a large number of instances of one type."""
    services = Services()

    for i in range(1000):
        services.add(ServiceA(i))

    provider = services.provider()

    assert len(provider) == 1000
    assert provider.get(ServiceA).value == 0  # First registered


def test_many_different_types() -> None:
    """Test handling many different service types."""
    services = Services()

    for i in range(100):
        service_type = type(f"Service{i}", (), {"value": i})
        services.add(service_type())

    provider = services.provider()

    assert len(provider) == 100
    assert len(provider.get_all_types()) == 100


# ==================== Thread Safety ====================


def test_provider_concurrent_reads() -> None:
    """Test that a provider handles concurrent reads safely."""
    services = Services()
    for i in range(100):
        services.add(type(f"S{i}", (), {})())

    provider = services.provider()

    errors: list[Exception] = []

    def reader() -> None:
        try:
            for _ in range(10):
                assert len(provider) == 100
                assert len(provider.get_all_types()) == 100
        except Exception as e:  # pragma: no cover - only on failure
            errors.append(e)

    threads = [threading.Thread(target=reader) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []


def test_collection_mutation_during_provider_use() -> None:
    """Test that mutating the collection doesn't affect an existing provider."""
    services = Services()
    services.add(ServiceA(1))

    provider = services.provider()

    def mutator() -> None:
        services.add(ServiceA(2))
        services.add(ServiceB("test"))

    thread = threading.Thread(target=mutator)
    thread.start()
    thread.join()

    assert len(provider) == 1
