"""Comprehensive edge case tests for ServiceCollection and ServiceProvider.

Tests cover advanced scenarios including:
- Diamond inheritance (multiple inheritance problem)
- Multiple inheritance
- Mixins
- Primitives and built-in types
- Abstract base classes
- Same instance registered multiple times
- Deep inheritance hierarchies
- Thread safety verification
- Complex registration order scenarios
- Protocol support
"""

import threading
from abc import ABC, abstractmethod
from typing import Protocol, runtime_checkable

import pytest

from pymediate.service import ServiceCollection, ServiceNotFoundError

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
    services = ServiceCollection()
    bat = Bat("Batman")

    services.add(bat)
    provider = services.build_provider()

    # Should be able to resolve by exact type
    assert provider.resolve(Bat) is bat

    # Should resolve through all inheritance paths
    all_mammals = provider.resolve_all(Mammal)
    assert bat in all_mammals

    all_winged = provider.resolve_all(WingedAnimal)
    assert bat in all_winged

    all_animals = provider.resolve_all(Animal)
    assert bat in all_animals


def test_diamond_inheritance_multiple_instances() -> None:
    """Test diamond inheritance with multiple instances."""
    services = ServiceCollection()
    bat1 = Bat("Bat1")
    bat2 = Bat("Bat2")
    mammal = Mammal("Mammal")
    winged = WingedAnimal("Bird")

    services.add(bat1)
    services.add(mammal)
    services.add(winged)
    services.add(bat2)

    provider = services.build_provider()

    # Resolve all animals - should get all in order
    all_animals = provider.resolve_all(Animal)
    assert len(all_animals) == 4
    assert all_animals[0] is bat1
    assert all_animals[1] is mammal
    assert all_animals[2] is winged
    assert all_animals[3] is bat2

    # Resolve all mammals - should get bats and mammal
    all_mammals = provider.resolve_all(Mammal)
    assert len(all_mammals) == 3
    assert bat1 in all_mammals
    assert bat2 in all_mammals
    assert mammal in all_mammals


def test_diamond_inheritance_mro_order() -> None:
    """Test that MRO (Method Resolution Order) is respected."""
    services = ServiceCollection()
    bat = Bat()

    services.add(bat)
    provider = services.build_provider()

    # Bat should be instance of all types in MRO
    assert isinstance(bat, Bat)
    assert isinstance(bat, Mammal)
    assert isinstance(bat, WingedAnimal)
    assert isinstance(bat, Animal)

    # resolve_all should work for any type in MRO
    assert len(provider.resolve_all(Bat)) == 1
    assert len(provider.resolve_all(Mammal)) == 1
    assert len(provider.resolve_all(WingedAnimal)) == 1
    assert len(provider.resolve_all(Animal)) == 1


# ==================== Mixin Tests ====================


def test_mixin_resolution() -> None:
    """Test resolving services with mixins."""
    services = ServiceCollection()
    logged = LoggedService(1)
    timestamped = TimestampedService(2)
    full = FullyDecoratedService(3)

    services.add(logged)
    services.add(timestamped)
    services.add(full)

    provider = services.build_provider()

    # Resolve by exact type
    assert provider.resolve(LoggedService) is logged

    # Resolve by base service
    all_services = provider.resolve_all(Service)
    assert len(all_services) == 3

    # Resolve by mixin - mixins are classes too!
    all_logged = provider.resolve_all(LoggingMixin)
    assert len(all_logged) == 2
    assert logged in all_logged
    assert full in all_logged

    all_timestamped = provider.resolve_all(TimestampMixin)
    assert len(all_timestamped) == 2
    assert timestamped in all_timestamped
    assert full in all_timestamped


def test_mixin_registration_order() -> None:
    """Test that registration order is preserved with mixins."""
    services = ServiceCollection()
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

    provider = services.build_provider()

    # Resolve by mixin should preserve global order
    all_logging = provider.resolve_all(LoggingMixin)
    assert len(all_logging) == 3
    assert all_logging[0] is l1  # Registered 2nd
    assert all_logging[1] is f1  # Registered 4th
    assert all_logging[2] is l2  # Registered 5th


# ==================== Primitive Type Tests ====================


def test_primitive_types() -> None:
    """Test registering primitive types."""
    services = ServiceCollection()
    services.add(42)
    services.add(3.14)
    services.add("hello")
    services.add(True)
    services.add([1, 2, 3])
    services.add({"key": "value"})

    provider = services.build_provider()

    # Each primitive type should be resolvable
    assert provider.resolve(int) == 42
    assert provider.resolve(float) == 3.14
    assert provider.resolve(str) == "hello"
    assert provider.resolve(bool) is True  # Note: bool is subclass of int!
    assert provider.resolve(list) == [1, 2, 3]
    assert provider.resolve(dict) == {"key": "value"}


def test_bool_int_inheritance() -> None:
    """Test that bool is treated as int subclass (Python quirk)."""
    services = ServiceCollection()
    services.add(True)
    services.add(42)

    provider = services.build_provider()

    # bool is subclass of int in Python
    all_ints = provider.resolve_all(int)
    assert len(all_ints) == 2
    assert True in all_ints
    assert 42 in all_ints

    # Exact type matching: bool and int are separate types
    assert provider.resolve(bool) is True
    assert provider.resolve(int) == 42  # First instance of exact type int


def test_multiple_primitives_same_type() -> None:
    """Test multiple instances of same primitive type."""
    services = ServiceCollection()
    services.add(1)
    services.add(2)
    services.add(3)

    provider = services.build_provider()

    assert provider.resolve(int) == 1  # First one
    all_ints = provider.resolve_all(int)
    assert all_ints == (1, 2, 3)


# ==================== ABC Tests ====================


def test_abstract_base_class() -> None:
    """Test with abstract base classes."""
    services = ServiceCollection()
    impl = ConcreteServiceImpl()

    services.add(impl)
    provider = services.build_provider()

    # Can resolve by concrete type
    assert provider.resolve(ConcreteServiceImpl) is impl

    # Can resolve by abstract base class
    all_abstract = provider.resolve_all(AbstractService)  # type: ignore[type-abstract]
    assert len(all_abstract) == 1
    assert impl in all_abstract

    # Cannot resolve abstract class directly (not registered)
    with pytest.raises(ServiceNotFoundError):
        provider.resolve(AbstractService)  # type: ignore[type-abstract]


def test_multiple_abc_implementations() -> None:
    """Test multiple implementations of same ABC."""
    services = ServiceCollection()

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

    provider = services.build_provider()

    # Both should be resolvable via ABC
    all_impls = provider.resolve_all(AbstractService)  # type: ignore[type-abstract]
    assert len(all_impls) == 2
    assert impl1 in all_impls
    assert impl2 in all_impls


# ==================== Protocol Tests ====================


def test_protocol_support() -> None:
    """Test with runtime checkable protocols."""
    services = ServiceCollection()
    circle = Circle()
    square = Square()

    services.add(circle)
    services.add(square)

    provider = services.build_provider()

    # Resolve by protocol
    all_drawable = provider.resolve_all(Drawable)  # type: ignore[type-abstract]
    assert len(all_drawable) == 2
    assert circle in all_drawable
    assert square in all_drawable

    # Exact type still works
    assert provider.resolve(Circle) is circle


def test_protocol_with_non_protocol_classes() -> None:
    """Test protocol resolution mixed with regular classes."""
    services = ServiceCollection()

    class NotDrawable:
        pass

    circle = Circle()
    not_drawable = NotDrawable()

    services.add(circle)
    services.add(not_drawable)

    provider = services.build_provider()

    # Only protocol implementers should match
    all_drawable = provider.resolve_all(Drawable)  # type: ignore[type-abstract]
    assert len(all_drawable) == 1
    assert circle in all_drawable


# ==================== Same Instance Multiple Registrations ====================


def test_same_instance_registered_twice() -> None:
    """Test registering the same instance multiple times."""
    services = ServiceCollection()
    singleton = Service(42)

    services.add(singleton)
    services.add(singleton)
    services.add(singleton)

    provider = services.build_provider()

    # Should have 3 references to same instance
    assert len(provider) == 3

    all_services = provider.resolve_all(Service)
    assert len(all_services) == 3
    assert all_services[0] is singleton
    assert all_services[1] is singleton
    assert all_services[2] is singleton

    # Resolve returns first (which is the singleton)
    assert provider.resolve(Service) is singleton


def test_same_instance_identity_preserved() -> None:
    """Test that instance identity is preserved through resolution."""
    services = ServiceCollection()
    singleton = Service(42)

    services.add(singleton)
    provider = services.build_provider()

    resolved = provider.resolve(Service)
    assert resolved is singleton  # Same object, not a copy


# ==================== Deep Inheritance Tests ====================


def test_deep_inheritance_hierarchy() -> None:
    """Test with very deep inheritance hierarchy."""
    services = ServiceCollection()
    level5 = Level5()

    services.add(level5)
    provider = services.build_provider()

    # Should resolve through all levels
    assert len(provider.resolve_all(Level0)) == 1
    assert len(provider.resolve_all(Level1)) == 1
    assert len(provider.resolve_all(Level2)) == 1
    assert len(provider.resolve_all(Level3)) == 1
    assert len(provider.resolve_all(Level4)) == 1
    assert len(provider.resolve_all(Level5)) == 1


def test_deep_inheritance_multiple_levels() -> None:
    """Test resolving instances at different levels."""
    services = ServiceCollection()
    l2 = Level2()
    l4 = Level4()
    l5 = Level5()

    services.add(l2)
    services.add(l4)
    services.add(l5)

    provider = services.build_provider()

    # Level0: all inherit from it
    assert len(provider.resolve_all(Level0)) == 3

    # Level2: only l2, l4, l5 inherit
    all_l2 = provider.resolve_all(Level2)
    assert len(all_l2) == 3
    assert l2 in all_l2
    assert l4 in all_l2
    assert l5 in all_l2

    # Level4: only l4 and l5
    all_l4 = provider.resolve_all(Level4)
    assert len(all_l4) == 2
    assert l4 in all_l4
    assert l5 in all_l4

    # Level5: only l5
    assert len(provider.resolve_all(Level5)) == 1


# ==================== Thread Safety Tests ====================


def test_provider_concurrent_reads() -> None:
    """Test that provider can handle concurrent reads safely."""
    services = ServiceCollection()
    for i in range(100):
        services.add(Service(i))

    provider = services.build_provider()

    results = []
    errors = []

    def reader() -> None:
        try:
            for _ in range(10):
                all_services = provider.resolve_all(Service)
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
    services = ServiceCollection()
    services.add(Service(1))

    provider = services.build_provider()

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
    services = ServiceCollection()

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

    provider = services.build_provider()

    # resolve_all(Level0) should return in registration order, not hierarchy order
    all_l0 = provider.resolve_all(Level0)
    assert len(all_l0) == 6
    assert all_l0[0] is l0
    assert all_l0[1] is l2
    assert all_l0[2] is l1
    assert all_l0[3] is l4
    assert all_l0[4] is l3
    assert all_l0[5] is l5


def test_interleaved_type_registration() -> None:
    """Test interleaved registration of different type hierarchies."""
    services = ServiceCollection()

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

    provider = services.build_provider()

    # Each hierarchy should maintain its registration order
    all_animals = provider.resolve_all(Animal)
    assert len(all_animals) == 3
    assert all_animals[0] is a1
    assert all_animals[1] is m1
    assert all_animals[2] is b1

    all_services = provider.resolve_all(Service)
    assert len(all_services) == 3
    assert all_services[0] is s1
    assert all_services[1] is ls1
    assert all_services[2] is ts1


# ==================== Empty and Edge Cases ====================


def test_resolve_all_with_no_matches() -> None:
    """Test resolve_all when no instances match."""
    services = ServiceCollection()
    services.add(Service(1))

    provider = services.build_provider()

    # Querying unrelated type returns empty
    result = provider.resolve_all(Animal)
    assert result == ()
    assert len(result) == 0


def test_type_with_no_instances() -> None:
    """Test exact type check when no instances exist."""
    services = ServiceCollection()
    services.add(Service(1))

    provider = services.build_provider()

    assert not provider.has(Animal)

    with pytest.raises(ServiceNotFoundError):
        provider.resolve(Animal)


def test_none_type_handling() -> None:
    """Test that None is properly rejected."""
    services = ServiceCollection()

    with pytest.raises(ValueError, match="Cannot register None"):
        services.add(None)


# ==================== Type Identity Tests ====================


def test_type_identity_with_generics() -> None:
    """Test that generic types with same origin are treated as same type."""
    services = ServiceCollection()

    # In Python, list[int] and list[str] both resolve to 'list' at runtime
    list_int = [1, 2, 3]
    list_str = ["a", "b"]

    services.add(list_int)
    services.add(list_str)

    provider = services.build_provider()

    # Both are just 'list' at runtime
    assert len(provider.resolve_all(list)) == 2


def test_object_base_class() -> None:
    """Test resolving by object base class (everything inherits from object)."""
    services = ServiceCollection()
    s1 = Service(1)
    a1 = Animal("test")
    num = 42

    services.add(s1)
    services.add(a1)
    services.add(num)

    provider = services.build_provider()

    # Everything is an instance of object
    all_objects = provider.resolve_all(object)
    assert len(all_objects) == 3


# ==================== Error Message Tests ====================


def test_error_message_clarity() -> None:
    """Test that error messages are clear and helpful."""
    services = ServiceCollection()
    services.add(Service(1))
    services.add(Animal("test"))

    provider = services.build_provider()

    try:
        provider.resolve(Mammal)
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
    services = ServiceCollection()
    services.add(Service(1))

    provider1 = services.build_provider()

    services.add(Service(2))

    provider2 = services.build_provider()

    # Providers should have different snapshots
    assert len(provider1) == 1
    assert len(provider2) == 2

    # They should be different objects
    assert provider1 is not provider2


def test_clear_and_rebuild() -> None:
    """Test clearing collection and building new provider."""
    services = ServiceCollection()
    services.add(Service(1))

    provider1 = services.build_provider()

    services.clear()
    services.add(Animal("test"))

    provider2 = services.build_provider()

    # provider1 should still have original service
    assert provider1.has(Service)
    assert not provider1.has(Animal)

    # provider2 should have only new service
    assert not provider2.has(Service)
    assert provider2.has(Animal)
