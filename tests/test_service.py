"""Comprehensive tests for Services and ServiceProvider.

Tests cover:
- Basic registration and resolution
- Multiple instances per type
- Registration order preservation
- Inheritance support
- Immutability of ServiceProvider
- Error handling
- Edge cases
- Diamond inheritance (multiple inheritance problem)
- Mixins
- Primitives and built-in types
- Abstract base classes
- Deep inheritance hierarchies
- Thread safety verification
- Protocol support
"""

import threading
from abc import ABC, abstractmethod
from typing import Protocol, runtime_checkable

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
    assert hasattr(provider, "get")
    assert hasattr(provider, "get_all")
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
    resolved = provider.get(ServiceA)

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
    resolved = provider.get(ServiceA)

    assert resolved is service_a1
    assert resolved.value == 1


def test_resolve_nonexistent_raises_error() -> None:
    """Test that resolving unregistered type raises ServiceNotFoundError."""
    services = Services()
    services.add(ServiceA(1))

    provider = services.provider()

    with pytest.raises(ServiceNotFoundError) as exc_info:
        provider.get(ServiceB)

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
    all_services = provider.get_all(ServiceA)

    assert len(all_services) == 3
    assert all_services[0] is service_a1
    assert all_services[1] is service_a2
    assert all_services[2] is service_a3


def test_resolve_all_empty() -> None:
    """Test resolve_all() returns empty tuple for unregistered type."""
    services = Services()
    services.add(ServiceA(1))

    provider = services.provider()
    all_services = provider.get_all(ServiceB)

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
    all_a = provider.get_all(ServiceA)

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
    all_base = provider.get_all(BaseService)

    assert len(all_base) == 2
    assert concrete_a in all_base
    assert concrete_b in all_base


def test_resolve_all_inheritance_returns_every_match() -> None:
    """Test that inheritance resolution returns every matching instance.

    Cross-type order is unspecified, but instances of the same concrete type keep
    their relative registration order.
    """
    services = Services()
    concrete_a1 = ConcreteServiceA(1, "first")
    concrete_b1 = ConcreteServiceB(2, "B1")
    concrete_a2 = ConcreteServiceA(3, "second")

    services.add(concrete_a1)
    services.add(concrete_b1)
    services.add(concrete_a2)

    provider = services.provider()
    all_base = provider.get_all(BaseService)

    assert len(all_base) == 3
    assert set(all_base) == {concrete_a1, concrete_b1, concrete_a2}
    # Same-type instances keep their relative registration order.
    a_instances = [s for s in all_base if type(s) is ConcreteServiceA]
    assert a_instances == [concrete_a1, concrete_a2]


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
    all_a = provider.get_all(ConcreteServiceA)

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
    all_base = provider.get_all(BaseService)
    assert len(all_base) == 2

    # Querying middle level should return it and its children
    all_concrete_a = provider.get_all(ConcreteServiceA)
    assert len(all_concrete_a) == 2
    assert concrete_a in all_concrete_a
    assert grandchild in all_concrete_a

    # Querying leaf level should return only that level
    all_grandchild = provider.get_all(GrandchildService)
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
        provider.get(BaseService)

    # But resolve_all() should work with inheritance
    all_base = provider.get_all(BaseService)
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
    assert len(provider.get_all(BaseService)) > 0


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
    all_a = provider.get_all(ServiceA)
    assert [s.value for s in all_a] == [1, 2, 3]

    all_b = provider.get_all(ServiceB)
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
    assert provider.get(ServiceA) is service_a
    assert len(provider.get_all(BaseService)) == 4  # All base service descendants
    assert len(provider.get_all(ConcreteServiceA)) == 3  # ConcreteServiceA + GrandchildService
    assert len(provider.get_all(ServiceA)) == 1


# ==================== Edge Cases and Error Handling ====================


def test_empty_collection_provider() -> None:
    """Test creating provider from empty collection."""
    services = Services()
    provider = services.provider()

    assert len(provider) == 0
    assert provider.get_all_types() == ()
    assert provider.get_all(ServiceA) == ()


def test_multiple_providers_from_same_collection() -> None:
    """Test that multiple providers can be created from same collection."""
    services = Services()
    services.add(ServiceA(1))

    provider1 = services.provider()
    provider2 = services.provider()

    # Both providers should work independently
    assert provider1.get(ServiceA).value == 1
    assert provider2.get(ServiceA).value == 1

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
    assert len(provider1.get_all(ServiceA)) == 1

    # provider2 should have all services
    assert len(provider2) == 3
    assert len(provider2.get_all(ServiceA)) == 2


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
        provider.get(ConcreteServiceA)
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
    resolved: ServiceA = provider.get(ServiceA)

    assert isinstance(resolved, ServiceA)
    assert resolved.value == 42


def test_resolve_all_returns_correct_sequence_type() -> None:
    """Test that resolve_all() returns properly typed sequence."""
    services = Services()
    services.add(ServiceA(1))
    services.add(ServiceA(2))

    provider = services.provider()
    all_services = provider.get_all(ServiceA)

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
    assert len(provider.get_all(ServiceA)) == 1000
    assert provider.get(ServiceA).value == 0  # First one


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


# ==================== Inheritance Test Fixtures ====================


class Animal:
    """Base animal class for diamond inheritance testing."""

    def __init__(self, name: str = "animal") -> None:
        self.name = name
        self.animal_init = True


class Mammal(Animal):
    """Mammal branch of diamond."""

    def __init__(self, name: str = "mammal") -> None:
        super().__init__(name)
        self.mammal_init = True


class WingedAnimal(Animal):
    """Winged animal branch of diamond."""

    def __init__(self, name: str = "winged") -> None:
        super().__init__(name)
        self.winged_init = True


class Bat(Mammal, WingedAnimal):
    """Diamond inheritance: Bat is both Mammal and WingedAnimal."""

    def __init__(self, name: str = "bat") -> None:
        super().__init__(name)
        self.bat_init = True


# ==================== Mixin Test Fixtures ====================


class LoggingMixin:
    """Mixin providing logging functionality."""

    def log(self, message: str) -> str:
        return f"LOG: {message}"


class TimestampMixin:
    """Mixin providing timestamp functionality."""

    def timestamp(self) -> str:
        return "2024-01-01"


class Service:
    """Base service class."""

    def __init__(self, id: int) -> None:
        self.id = id


class LoggedService(LoggingMixin, Service):
    """Service with logging mixin."""

    def __init__(self, id: int) -> None:
        super().__init__(id)


class TimestampedService(TimestampMixin, Service):
    """Service with timestamp mixin."""

    def __init__(self, id: int) -> None:
        super().__init__(id)


class FullyDecoratedService(LoggingMixin, TimestampMixin, Service):
    """Service with multiple mixins."""

    def __init__(self, id: int) -> None:
        super().__init__(id)


# ==================== ABC Test Fixtures ====================


class AbstractService(ABC):
    """Abstract base class."""

    @abstractmethod
    def execute(self) -> str:
        """Execute the service."""
        ...


class ConcreteServiceImpl(AbstractService):
    """Concrete implementation of abstract service."""

    def execute(self) -> str:
        return "executed"


# ==================== Protocol Test Fixtures ====================


@runtime_checkable
class Drawable(Protocol):
    """Protocol for drawable objects."""

    def draw(self) -> str:
        """Draw the object."""
        ...


class Circle:
    """Circle implements Drawable protocol."""

    def draw(self) -> str:
        return "circle"


class Square:
    """Square implements Drawable protocol."""

    def draw(self) -> str:
        return "square"


# ==================== Deep Inheritance Test Fixtures ====================


class Level0:
    """Root of deep hierarchy."""

    level = 0


class Level1(Level0):
    level = 1


class Level2(Level1):
    level = 2


class Level3(Level2):
    level = 3


class Level4(Level3):
    level = 4


class Level5(Level4):
    level = 5


# ==================== Diamond Inheritance Tests ====================


def test_diamond_inheritance_registration() -> None:
    """Test registering services with diamond inheritance."""
    services = Services()
    bat = Bat("Batman")

    services.add(bat)
    provider = services.provider()

    # Should be able to resolve by exact type
    assert provider.get(Bat) is bat

    # Should resolve through all inheritance paths
    all_mammals = provider.get_all(Mammal)
    assert bat in all_mammals

    all_winged = provider.get_all(WingedAnimal)
    assert bat in all_winged

    all_animals = provider.get_all(Animal)
    assert bat in all_animals


def test_diamond_inheritance_multiple_instances() -> None:
    """Test diamond inheritance with multiple instances."""
    services = Services()
    bat1 = Bat("Bat1")
    bat2 = Bat("Bat2")
    mammal = Mammal("Mammal")
    winged = WingedAnimal("Bird")

    services.add(bat1)
    services.add(mammal)
    services.add(winged)
    services.add(bat2)

    provider = services.provider()

    # Resolve all animals - should get every match (cross-type order unspecified)
    all_animals = provider.get_all(Animal)
    assert len(all_animals) == 4
    assert set(all_animals) == {bat1, mammal, winged, bat2}
    # Same-type instances keep their relative registration order.
    bats = [a for a in all_animals if type(a) is Bat]
    assert bats == [bat1, bat2]

    # Resolve all mammals - should get bats and mammal
    all_mammals = provider.get_all(Mammal)
    assert len(all_mammals) == 3
    assert bat1 in all_mammals
    assert bat2 in all_mammals
    assert mammal in all_mammals


def test_diamond_inheritance_mro_order() -> None:
    """Test that MRO (Method Resolution Order) is respected."""
    services = Services()
    bat = Bat()

    services.add(bat)
    provider = services.provider()

    # Bat should be instance of all types in MRO
    assert isinstance(bat, Bat)
    assert isinstance(bat, Mammal)
    assert isinstance(bat, WingedAnimal)
    assert isinstance(bat, Animal)

    # resolve_all should work for any type in MRO
    assert len(provider.get_all(Bat)) == 1
    assert len(provider.get_all(Mammal)) == 1
    assert len(provider.get_all(WingedAnimal)) == 1
    assert len(provider.get_all(Animal)) == 1


# ==================== Mixin Tests ====================


def test_mixin_resolution() -> None:
    """Test resolving services with mixins."""
    services = Services()
    logged = LoggedService(1)
    timestamped = TimestampedService(2)
    full = FullyDecoratedService(3)

    services.add(logged)
    services.add(timestamped)
    services.add(full)

    provider = services.provider()

    # Resolve by exact type
    assert provider.get(LoggedService) is logged

    # Resolve by base service
    all_services = provider.get_all(Service)
    assert len(all_services) == 3

    # Resolve by mixin - mixins are classes too!
    all_logged = provider.get_all(LoggingMixin)
    assert len(all_logged) == 2
    assert logged in all_logged
    assert full in all_logged

    all_timestamped = provider.get_all(TimestampMixin)
    assert len(all_timestamped) == 2
    assert timestamped in all_timestamped
    assert full in all_timestamped


def test_mixin_resolution_returns_every_match() -> None:
    """Test that resolving by a mixin returns every matching instance.

    Cross-type order is unspecified; same-type instances keep their relative
    registration order.
    """
    services = Services()
    s1 = Service(1)
    l1 = LoggedService(2)
    t1 = TimestampedService(3)
    f1 = FullyDecoratedService(4)
    l2 = LoggedService(5)

    services.add(s1)
    services.add(l1)
    services.add(t1)
    services.add(f1)
    services.add(l2)

    provider = services.provider()

    all_logging = provider.get_all(LoggingMixin)
    assert len(all_logging) == 3
    assert set(all_logging) == {l1, f1, l2}
    # Same-type instances keep their relative registration order.
    logged = [s for s in all_logging if type(s) is LoggedService]
    assert logged == [l1, l2]


# ==================== Primitive Type Tests ====================


def test_primitive_types() -> None:
    """Test registering primitive types."""
    services = Services()
    services.add(42)
    services.add(3.14)
    services.add("hello")
    services.add(True)
    services.add([1, 2, 3])
    services.add({"key": "value"})

    provider = services.provider()

    # Each primitive type should be resolvable
    assert provider.get(int) == 42
    assert provider.get(float) == 3.14
    assert provider.get(str) == "hello"
    assert provider.get(bool) is True  # Note: bool is subclass of int!
    assert provider.get(list) == [1, 2, 3]
    assert provider.get(dict) == {"key": "value"}


def test_bool_int_inheritance() -> None:
    """Test that bool is treated as int subclass (Python quirk)."""
    services = Services()
    services.add(True)
    services.add(42)

    provider = services.provider()

    # bool is subclass of int in Python
    all_ints = provider.get_all(int)
    assert len(all_ints) == 2
    assert True in all_ints
    assert 42 in all_ints

    # Exact type matching: bool and int are separate types
    assert provider.get(bool) is True
    assert provider.get(int) == 42  # First instance of exact type int


def test_multiple_primitives_same_type() -> None:
    """Test multiple instances of same primitive type."""
    services = Services()
    services.add(1)
    services.add(2)
    services.add(3)

    provider = services.provider()

    assert provider.get(int) == 1  # First one
    all_ints = provider.get_all(int)
    assert all_ints == (1, 2, 3)


# ==================== ABC Tests ====================


def test_abstract_base_class() -> None:
    """Test with abstract base classes."""
    services = Services()
    impl = ConcreteServiceImpl()

    services.add(impl)
    provider = services.provider()

    # Can resolve by concrete type
    assert provider.get(ConcreteServiceImpl) is impl

    # Can resolve by abstract base class
    all_abstract = provider.get_all(AbstractService)  # type: ignore[type-abstract]
    assert len(all_abstract) == 1
    assert impl in all_abstract

    # Cannot resolve abstract class directly (not registered)
    with pytest.raises(ServiceNotFoundError):
        provider.get(AbstractService)  # type: ignore[type-abstract]


def test_multiple_abc_implementations() -> None:
    """Test multiple implementations of same ABC."""
    services = Services()

    class Impl1(AbstractService):
        def execute(self) -> str:
            return "impl1"

    class Impl2(AbstractService):
        def execute(self) -> str:
            return "impl2"

    impl1 = Impl1()
    impl2 = Impl2()

    services.add(impl1)
    services.add(impl2)

    provider = services.provider()

    # Both should be resolvable via ABC
    all_impls = provider.get_all(AbstractService)  # type: ignore[type-abstract]
    assert len(all_impls) == 2
    assert impl1 in all_impls
    assert impl2 in all_impls


# ==================== Protocol Tests ====================


def test_protocol_support() -> None:
    """Test with runtime checkable protocols."""
    services = Services()
    circle = Circle()
    square = Square()

    services.add(circle)
    services.add(square)

    provider = services.provider()

    # Resolve by protocol
    all_drawable = provider.get_all(Drawable)  # type: ignore[type-abstract]
    assert len(all_drawable) == 2
    assert circle in all_drawable
    assert square in all_drawable

    # Exact type still works
    assert provider.get(Circle) is circle


def test_protocol_with_non_protocol_classes() -> None:
    """Test protocol resolution mixed with regular classes."""
    services = Services()

    class NotDrawable:
        pass

    circle = Circle()
    not_drawable = NotDrawable()

    services.add(circle)
    services.add(not_drawable)

    provider = services.provider()

    # Only protocol implementers should match
    all_drawable = provider.get_all(Drawable)  # type: ignore[type-abstract]
    assert len(all_drawable) == 1
    assert circle in all_drawable


# ==================== Same Instance Multiple Registrations ====================


def test_same_instance_registered_twice() -> None:
    """Test registering the same instance multiple times."""
    services = Services()
    singleton = Service(42)

    services.add(singleton)
    services.add(singleton)
    services.add(singleton)

    provider = services.provider()

    # Should have 3 references to same instance
    assert len(provider) == 3

    all_services = provider.get_all(Service)
    assert len(all_services) == 3
    assert all_services[0] is singleton
    assert all_services[1] is singleton
    assert all_services[2] is singleton

    # Resolve returns first (which is the singleton)
    assert provider.get(Service) is singleton


def test_same_instance_identity_preserved() -> None:
    """Test that instance identity is preserved through resolution."""
    services = Services()
    singleton = Service(42)

    services.add(singleton)
    provider = services.provider()

    resolved = provider.get(Service)
    assert resolved is singleton  # Same object, not a copy


# ==================== Deep Inheritance Tests ====================


def test_deep_inheritance_hierarchy() -> None:
    """Test with very deep inheritance hierarchy."""
    services = Services()
    level5 = Level5()

    services.add(level5)
    provider = services.provider()

    # Should resolve through all levels
    assert len(provider.get_all(Level0)) == 1
    assert len(provider.get_all(Level1)) == 1
    assert len(provider.get_all(Level2)) == 1
    assert len(provider.get_all(Level3)) == 1
    assert len(provider.get_all(Level4)) == 1
    assert len(provider.get_all(Level5)) == 1


def test_deep_inheritance_multiple_levels() -> None:
    """Test resolving instances at different levels."""
    services = Services()
    l2 = Level2()
    l4 = Level4()
    l5 = Level5()

    services.add(l2)
    services.add(l4)
    services.add(l5)

    provider = services.provider()

    # Level0: all inherit from it
    assert len(provider.get_all(Level0)) == 3

    # Level2: only l2, l4, l5 inherit
    all_l2 = provider.get_all(Level2)
    assert len(all_l2) == 3
    assert l2 in all_l2
    assert l4 in all_l2
    assert l5 in all_l2

    # Level4: only l4 and l5
    all_l4 = provider.get_all(Level4)
    assert len(all_l4) == 2
    assert l4 in all_l4
    assert l5 in all_l4

    # Level5: only l5
    assert len(provider.get_all(Level5)) == 1


# ==================== Thread Safety Tests ====================


def test_provider_concurrent_reads() -> None:
    """Test that provider can handle concurrent reads safely."""
    services = Services()
    for i in range(100):
        services.add(Service(i))

    provider = services.provider()

    results = []
    errors = []

    def reader() -> None:
        try:
            for _ in range(10):
                all_services = provider.get_all(Service)
                results.append(len(all_services))
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=reader) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # No errors should occur
    assert len(errors) == 0

    # All reads should return same count
    assert all(count == 100 for count in results)


def test_collection_mutation_during_provider_use() -> None:
    """Test that mutating collection doesn't affect existing provider."""
    services = Services()
    services.add(Service(1))

    provider = services.provider()

    # Mutate collection in different thread
    def mutator() -> None:
        services.add(Service(2))
        services.add(Service(3))

    thread = threading.Thread(target=mutator)
    thread.start()
    thread.join()

    # Provider should still only have original service
    assert len(provider) == 1


# ==================== Complex Registration Order Tests ====================


def test_complex_inheritance_registration_order() -> None:
    """Test complex scenario with mixed inheritance and registration order."""
    services = Services()

    # Register in specific order: L0, L2, L1, L4, L3, L5
    l0 = Level0()
    l2 = Level2()
    l1 = Level1()
    l4 = Level4()
    l3 = Level3()
    l5 = Level5()

    services.add(l0)
    services.add(l2)
    services.add(l1)
    services.add(l4)
    services.add(l3)
    services.add(l5)

    provider = services.provider()

    # resolve_all(Level0) should return in registration order, not hierarchy order
    all_l0 = provider.get_all(Level0)
    assert len(all_l0) == 6
    assert all_l0[0] is l0
    assert all_l0[1] is l2
    assert all_l0[2] is l1
    assert all_l0[3] is l4
    assert all_l0[4] is l3
    assert all_l0[5] is l5


def test_interleaved_type_registration() -> None:
    """Test interleaved registration of different type hierarchies."""
    services = Services()

    # Interleave Animal hierarchy with Service hierarchy
    a1 = Animal("a1")
    s1 = Service(1)
    m1 = Mammal("m1")
    ls1 = LoggedService(2)
    b1 = Bat("b1")
    ts1 = TimestampedService(3)

    services.add(a1)
    services.add(s1)
    services.add(m1)
    services.add(ls1)
    services.add(b1)
    services.add(ts1)

    provider = services.provider()

    # Each hierarchy should maintain its registration order
    all_animals = provider.get_all(Animal)
    assert len(all_animals) == 3
    assert all_animals[0] is a1
    assert all_animals[1] is m1
    assert all_animals[2] is b1

    all_services = provider.get_all(Service)
    assert len(all_services) == 3
    assert all_services[0] is s1
    assert all_services[1] is ls1
    assert all_services[2] is ts1


# ==================== Empty and Edge Cases ====================


def test_resolve_all_with_no_matches() -> None:
    """Test resolve_all when no instances match."""
    services = Services()
    services.add(Service(1))

    provider = services.provider()

    # Querying unrelated type returns empty
    result = provider.get_all(Animal)
    assert result == ()
    assert len(result) == 0


def test_type_with_no_instances() -> None:
    """Test exact type check when no instances exist."""
    services = Services()
    services.add(Service(1))

    provider = services.provider()

    assert not provider.has(Animal)

    with pytest.raises(ServiceNotFoundError):
        provider.get(Animal)


def test_none_type_handling() -> None:
    """Test that None is properly rejected."""
    services = Services()

    with pytest.raises(ValueError, match="Cannot register None"):
        services.add(None)


# ==================== Type Identity Tests ====================


def test_type_identity_with_generics() -> None:
    """Test that generic types with same origin are treated as same type."""
    services = Services()

    # In Python, list[int] and list[str] both resolve to 'list' at runtime
    list_int = [1, 2, 3]
    list_str = ["a", "b"]

    services.add(list_int)
    services.add(list_str)

    provider = services.provider()

    # Both are just 'list' at runtime
    assert len(provider.get_all(list)) == 2


def test_object_base_class() -> None:
    """Test resolving by object base class (everything inherits from object)."""
    services = Services()
    s1 = Service(1)
    a1 = Animal("test")
    num = 42

    services.add(s1)
    services.add(a1)
    services.add(num)

    provider = services.provider()

    # Everything is an instance of object
    all_objects = provider.get_all(object)
    assert len(all_objects) == 3


# ==================== Error Message Tests ====================


def test_error_message_clarity() -> None:
    """Test that error messages are clear and helpful."""
    services = Services()
    services.add(Service(1))
    services.add(Animal("test"))

    provider = services.provider()

    try:
        provider.get(Mammal)
        pytest.fail("Should have raised ServiceNotFoundError")
    except ServiceNotFoundError as e:
        # Error should include requested type
        assert "Mammal" in str(e)
        # Error should include available types
        assert "Service" in str(e)
        assert "Animal" in str(e)
        # Error should have proper attributes
        assert e.service_type == Mammal
        assert Service in e.available_types
        assert Animal in e.available_types


# ==================== Provider Independence Tests ====================


def test_multiple_providers_independence() -> None:
    """Test that multiple providers from same collection are independent."""
    services = Services()
    services.add(Service(1))

    provider1 = services.provider()

    services.add(Service(2))

    provider2 = services.provider()

    # Providers should have different snapshots
    assert len(provider1) == 1
    assert len(provider2) == 2

    # They should be different objects
    assert provider1 is not provider2


def test_clear_and_rebuild() -> None:
    """Test clearing collection and building new provider."""
    services = Services()
    services.add(Service(1))

    provider1 = services.provider()

    services.clear()
    services.add(Animal("test"))

    provider2 = services.provider()

    # provider1 should still have original service
    assert provider1.has(Service)
    assert not provider1.has(Animal)

    # provider2 should have only new service
    assert not provider2.has(Service)
    assert provider2.has(Animal)
