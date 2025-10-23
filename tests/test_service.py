"""Comprehensive tests for Services and ServiceProvider.

Tests cover:
- Basic registration and resolution
- Multiple instances per type
- Registration order preservation
- Inheritance support
- Immutability of ServiceProvider
- Error handling
- Edge cases
"""

import pytest

from pymediate.service import ServiceNotFoundError, Services


# Test fixtures - various service classes for testing
class ServiceA:
    """Simple service for testing."""

    def __init__(self, value: int = 1) -> None:
        self.value = value


class ServiceB:
    """Another simple service for testing."""

    def __init__(self, name: str = "B") -> None:
        self.name = name


class BaseService:
    """Base service class for inheritance testing."""

    def __init__(self, id: int) -> None:
        self.id = id


class ConcreteServiceA(BaseService):
    """Concrete service A inheriting from BaseService."""

    def __init__(self, id: int, extra: str = "A") -> None:
        super().__init__(id)
        self.extra = extra


class ConcreteServiceB(BaseService):
    """Concrete service B inheriting from BaseService."""

    def __init__(self, id: int, extra: str = "B") -> None:
        super().__init__(id)
        self.extra = extra


class GrandchildService(ConcreteServiceA):
    """Grandchild service for multi-level inheritance testing."""

    def __init__(self, id: int, extra: str = "grand") -> None:
        super().__init__(id, extra)


# ==================== Services Tests ====================


def test_collection_initialization() -> None:
    """Test that Services initializes empty."""
    services = Services()

    assert len(services) == 0
    assert repr(services) == "Services(services={}, total=0)"


def test_add_single_service() -> None:
    """Test adding a single service instance."""
    services = Services()
    service_a = ServiceA(42)

    result = services.add(service_a)

    assert result is services  # Method chaining
    assert len(services) == 1


def test_add_multiple_different_services() -> None:
    """Test adding multiple different service types."""
    services = Services()
    service_a = ServiceA(1)
    service_b = ServiceB("test")

    services.add(service_a)
    services.add(service_b)

    assert len(services) == 2


def test_add_multiple_same_type() -> None:
    """Test adding multiple instances of the same type."""
    services = Services()
    service_a1 = ServiceA(1)
    service_a2 = ServiceA(2)
    service_a3 = ServiceA(3)

    services.add(service_a1)
    services.add(service_a2)
    services.add(service_a3)

    assert len(services) == 3


def test_add_none_raises_error() -> None:
    """Test that adding None raises ValueError."""
    services = Services()

    with pytest.raises(ValueError, match="Cannot register None"):
        services.add(None)


def test_add_method_chaining() -> None:
    """Test that add() supports method chaining."""
    services = Services()
    service_a = ServiceA(1)
    service_b = ServiceB("test")

    result = services.add(service_a).add(service_b)

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

    # Provider should have all required methods
    assert hasattr(provider, "resolve")
    assert hasattr(provider, "resolve_all")
    assert hasattr(provider, "has")
    assert hasattr(provider, "get_all_types")
    assert len(provider) == 1


def test_provider_immutability() -> None:
    """Test that provider is immutable and not affected by collection changes."""
    services = Services()
    service_a = ServiceA(1)
    services.add(service_a)

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
    resolved = provider.resolve(ServiceA)

    assert resolved is service_a
    assert resolved.value == 42


def test_resolve_first_of_multiple() -> None:
    """Test that resolve() returns the first registered instance."""
    services = Services()
    service_a1 = ServiceA(1)
    service_a2 = ServiceA(2)
    service_a3 = ServiceA(3)

    services.add(service_a1)
    services.add(service_a2)
    services.add(service_a3)

    provider = services.provider()
    resolved = provider.resolve(ServiceA)

    assert resolved is service_a1
    assert resolved.value == 1


def test_resolve_nonexistent_raises_error() -> None:
    """Test that resolving unregistered type raises ServiceNotFoundError."""
    services = Services()
    services.add(ServiceA(1))

    provider = services.provider()

    with pytest.raises(ServiceNotFoundError) as exc_info:
        provider.resolve(ServiceB)

    assert exc_info.value.service_type == ServiceB
    assert ServiceA in exc_info.value.available_types
    assert "ServiceB" in str(exc_info.value)


def test_resolve_all_single_type() -> None:
    """Test resolve_all() with single type."""
    services = Services()
    service_a1 = ServiceA(1)
    service_a2 = ServiceA(2)
    service_a3 = ServiceA(3)

    services.add(service_a1)
    services.add(service_a2)
    services.add(service_a3)

    provider = services.provider()
    all_services = provider.resolve_all(ServiceA)

    assert len(all_services) == 3
    assert all_services[0] is service_a1
    assert all_services[1] is service_a2
    assert all_services[2] is service_a3


def test_resolve_all_empty() -> None:
    """Test resolve_all() returns empty tuple for unregistered type."""
    services = Services()
    services.add(ServiceA(1))

    provider = services.provider()
    all_services = provider.resolve_all(ServiceB)

    assert len(all_services) == 0
    assert all_services == ()


def test_resolve_all_preserves_registration_order() -> None:
    """Test that resolve_all() preserves global registration order."""
    services = Services()
    service_a1 = ServiceA(1)
    service_b1 = ServiceB("first")
    service_a2 = ServiceA(2)
    service_b2 = ServiceB("second")
    service_a3 = ServiceA(3)

    services.add(service_a1)
    services.add(service_b1)
    services.add(service_a2)
    services.add(service_b2)
    services.add(service_a3)

    provider = services.provider()
    all_a = provider.resolve_all(ServiceA)

    # Should get ServiceA instances in registration order
    assert len(all_a) == 3
    assert all_a[0].value == 1
    assert all_a[1].value == 2
    assert all_a[2].value == 3


def test_has_registered_type() -> None:
    """Test has() returns True for registered type."""
    services = Services()
    services.add(ServiceA(1))

    provider = services.provider()

    assert provider.has(ServiceA) is True


def test_has_unregistered_type() -> None:
    """Test has() returns False for unregistered type."""
    services = Services()
    services.add(ServiceA(1))

    provider = services.provider()

    assert provider.has(ServiceB) is False


def test_get_all_types() -> None:
    """Test get_all_types() returns all registered types."""
    services = Services()
    services.add(ServiceA(1))
    services.add(ServiceB("test"))
    services.add(ServiceA(2))  # Second instance

    provider = services.provider()
    all_types = provider.get_all_types()

    assert len(all_types) == 2
    assert ServiceA in all_types
    assert ServiceB in all_types


def test_provider_len() -> None:
    """Test len() on provider returns total instance count."""
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


# ==================== Inheritance Tests ====================


def test_resolve_all_with_inheritance() -> None:
    """Test resolve_all() resolves subclass instances when querying base class."""
    services = Services()
    concrete_a = ConcreteServiceA(1)
    concrete_b = ConcreteServiceB(2)

    services.add(concrete_a)
    services.add(concrete_b)

    provider = services.provider()
    all_base = provider.resolve_all(BaseService)

    assert len(all_base) == 2
    assert concrete_a in all_base
    assert concrete_b in all_base


def test_resolve_all_inheritance_order() -> None:
    """Test that inheritance resolution preserves registration order."""
    services = Services()
    concrete_a1 = ConcreteServiceA(1, "first")
    concrete_b1 = ConcreteServiceB(2, "B1")
    concrete_a2 = ConcreteServiceA(3, "second")

    services.add(concrete_a1)
    services.add(concrete_b1)
    services.add(concrete_a2)

    provider = services.provider()
    all_base = provider.resolve_all(BaseService)

    assert len(all_base) == 3
    assert all_base[0] is concrete_a1
    assert all_base[1] is concrete_b1
    assert all_base[2] is concrete_a2


def test_resolve_all_specific_subclass() -> None:
    """Test resolve_all() with specific subclass only returns that subclass."""
    services = Services()
    concrete_a1 = ConcreteServiceA(1)
    concrete_b1 = ConcreteServiceB(2)
    concrete_a2 = ConcreteServiceA(3)

    services.add(concrete_a1)
    services.add(concrete_b1)
    services.add(concrete_a2)

    provider = services.provider()
    all_a = provider.resolve_all(ConcreteServiceA)

    assert len(all_a) == 2
    assert concrete_a1 in all_a
    assert concrete_a2 in all_a
    assert concrete_b1 not in all_a  # type: ignore[comparison-overlap]


def test_resolve_all_multi_level_inheritance() -> None:
    """Test resolve_all() with multi-level inheritance."""
    services = Services()
    concrete_a = ConcreteServiceA(1)
    grandchild = GrandchildService(2)

    services.add(concrete_a)
    services.add(grandchild)

    provider = services.provider()

    # Querying base should return all descendants
    all_base = provider.resolve_all(BaseService)
    assert len(all_base) == 2

    # Querying middle level should return it and its children
    all_concrete_a = provider.resolve_all(ConcreteServiceA)
    assert len(all_concrete_a) == 2
    assert concrete_a in all_concrete_a
    assert grandchild in all_concrete_a

    # Querying leaf level should return only that level
    all_grandchild = provider.resolve_all(GrandchildService)
    assert len(all_grandchild) == 1
    assert grandchild in all_grandchild


def test_resolve_exact_type_no_inheritance() -> None:
    """Test that resolve() does NOT match subclasses (exact type only)."""
    services = Services()
    concrete_a = ConcreteServiceA(1)

    services.add(concrete_a)

    provider = services.provider()

    # resolve() should fail because it only looks for exact type
    with pytest.raises(ServiceNotFoundError):
        provider.resolve(BaseService)

    # But resolve_all() should work with inheritance
    all_base = provider.resolve_all(BaseService)
    assert len(all_base) == 1


def test_has_exact_type_no_inheritance() -> None:
    """Test that has() does NOT check subclasses (exact type only)."""
    services = Services()
    concrete_a = ConcreteServiceA(1)

    services.add(concrete_a)

    provider = services.provider()

    # has() checks exact type only
    assert provider.has(ConcreteServiceA) is True
    assert provider.has(BaseService) is False

    # But we can check subclasses with resolve_all
    assert len(provider.resolve_all(BaseService)) > 0


# ==================== Mixed Type Registration Tests ====================


def test_mixed_types_registration_order() -> None:
    """Test registration order is preserved across different types."""
    services = Services()

    # Register in specific order: A, B, A, B, A
    a1 = ServiceA(1)
    b1 = ServiceB("first")
    a2 = ServiceA(2)
    b2 = ServiceB("second")
    a3 = ServiceA(3)

    services.add(a1)
    services.add(b1)
    services.add(a2)
    services.add(b2)
    services.add(a3)

    provider = services.provider()

    # Verify per-type order
    all_a = provider.resolve_all(ServiceA)
    assert [s.value for s in all_a] == [1, 2, 3]

    all_b = provider.resolve_all(ServiceB)
    assert [s.name for s in all_b] == ["first", "second"]


def test_complex_registration_scenario() -> None:
    """Test complex scenario with mixed types and inheritance."""
    services = Services()

    # Mix concrete services, base services, and regular services
    service_a = ServiceA(100)
    concrete_a1 = ConcreteServiceA(1, "first")
    service_b = ServiceB("middle")
    concrete_b = ConcreteServiceB(2)
    concrete_a2 = ConcreteServiceA(3, "last")
    grandchild = GrandchildService(4)

    services.add(service_a)
    services.add(concrete_a1)
    services.add(service_b)
    services.add(concrete_b)
    services.add(concrete_a2)
    services.add(grandchild)

    provider = services.provider()

    # Verify various resolutions
    assert len(provider) == 6
    assert provider.resolve(ServiceA) is service_a
    assert len(provider.resolve_all(BaseService)) == 4  # All base service descendants
    assert len(provider.resolve_all(ConcreteServiceA)) == 3  # ConcreteServiceA + GrandchildService
    assert len(provider.resolve_all(ServiceA)) == 1


# ==================== Edge Cases and Error Handling ====================


def test_empty_collection_provider() -> None:
    """Test creating provider from empty collection."""
    services = Services()
    provider = services.provider()

    assert len(provider) == 0
    assert provider.get_all_types() == ()
    assert provider.resolve_all(ServiceA) == ()


def test_multiple_providers_from_same_collection() -> None:
    """Test that multiple providers can be created from same collection."""
    services = Services()
    services.add(ServiceA(1))

    provider1 = services.provider()
    provider2 = services.provider()

    # Both providers should work independently
    assert provider1.resolve(ServiceA).value == 1
    assert provider2.resolve(ServiceA).value == 1

    # They should be different instances
    assert provider1 is not provider2


def test_provider_snapshot_isolation() -> None:
    """Test that providers are true snapshots isolated from collection."""
    services = Services()
    services.add(ServiceA(1))

    provider1 = services.provider()

    services.add(ServiceA(2))
    services.add(ServiceB("test"))

    provider2 = services.provider()

    # provider1 should have only first service
    assert len(provider1) == 1
    assert len(provider1.resolve_all(ServiceA)) == 1

    # provider2 should have all services
    assert len(provider2) == 3
    assert len(provider2.resolve_all(ServiceA)) == 2


def test_clear_does_not_affect_existing_providers() -> None:
    """Test that clearing collection doesn't affect existing providers."""
    services = Services()
    services.add(ServiceA(1))

    provider = services.provider()

    services.clear()

    # Provider should still work
    assert len(provider) == 1
    assert provider.has(ServiceA)


def test_service_not_found_error_attributes() -> None:
    """Test ServiceNotFoundError has correct attributes."""
    services = Services()
    services.add(ServiceA(1))
    services.add(ServiceB("test"))

    provider = services.provider()

    try:
        provider.resolve(ConcreteServiceA)
        pytest.fail("Should have raised ServiceNotFoundError")
    except ServiceNotFoundError as e:
        assert e.service_type == ConcreteServiceA
        assert len(e.available_types) == 2
        assert ServiceA in e.available_types
        assert ServiceB in e.available_types


# ==================== Type Safety Tests ====================


def test_resolve_returns_correct_type() -> None:
    """Test that resolve() returns correctly typed instance."""
    services = Services()
    service = ServiceA(42)
    services.add(service)

    provider = services.provider()
    resolved: ServiceA = provider.resolve(ServiceA)

    assert isinstance(resolved, ServiceA)
    assert resolved.value == 42


def test_resolve_all_returns_correct_sequence_type() -> None:
    """Test that resolve_all() returns properly typed sequence."""
    services = Services()
    services.add(ServiceA(1))
    services.add(ServiceA(2))

    provider = services.provider()
    all_services = provider.resolve_all(ServiceA)

    assert isinstance(all_services, tuple)
    assert all(isinstance(s, ServiceA) for s in all_services)


# ==================== Performance and Large Scale Tests ====================


def test_large_number_of_services() -> None:
    """Test handling large number of services."""
    services = Services()

    # Register 1000 services
    for i in range(1000):
        services.add(ServiceA(i))

    provider = services.provider()

    assert len(provider) == 1000
    assert len(provider.resolve_all(ServiceA)) == 1000
    assert provider.resolve(ServiceA).value == 0  # First one


def test_many_different_types() -> None:
    """Test handling many different service types."""
    services = Services()

    # Create 100 different service types dynamically
    service_types = []
    for i in range(100):
        # Create a unique type
        service_type = type(f"Service{i}", (), {"value": i})
        service_types.append(service_type)
        services.add(service_type())

    provider = services.provider()

    assert len(provider) == 100
    assert len(provider.get_all_types()) == 100
