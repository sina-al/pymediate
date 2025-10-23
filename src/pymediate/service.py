"""Service collection and provider for dependency injection.

This module provides a simple but powerful service registration and resolution system
inspired by .NET's dependency injection, adapted for Python idioms.

Key Features:
    - Multiple instances per type
    - Inheritance support (resolve base class, get all subclass instances)
    - Registration order preservation
    - Immutable service provider
    - Type-safe resolution
    - Protocol-based extensibility

Example:
    ```python
    from pymediate.service import ServiceCollection

    # Build collection
    services = ServiceCollection()
    services.add(MyService())
    services.add(AnotherService())
    services.add(MyService())  # Register second instance

    # Create immutable provider
    provider = services.build_provider()

    # Resolve services
    all_services = provider.resolve_all(MyService)  # [instance1, instance2]
    first_service = provider.resolve(MyService)     # instance1
    has_service = provider.has(MyService)           # True
    ```

Architecture Notes:
    Why Two Data Structures?
    ========================
    The implementation uses both a dict and a list for different purposes:

    1. _services: dict[type, list[Any]]
       - Purpose: O(1) lookup for exact type matching
       - Used by: resolve(), has(), get_all_types()
       - Maps each type to ALL instances of that exact type

    2. _registration_order: list[tuple[type, Any]]
       - Purpose: Preserve global registration order across ALL types
       - Used by: resolve_all() for inheritance queries
       - Essential for "resolve_all(BaseClass)" to return subclasses in order

    Why not just OrderedDict?
    - dict is already ordered in Python 3.7+
    - OrderedDict maintains insertion order of KEYS, not values
    - We need to track MULTIPLE instances per key (type)
    - We need GLOBAL order across DIFFERENT keys for inheritance

    Example showing why we need both:
        services.add(ServiceA())  # global order: 0
        services.add(ServiceB())  # global order: 1
        services.add(ServiceA())  # global order: 2

        # _services: {ServiceA: [instance0, instance2], ServiceB: [instance1]}
        # _registration_order: [(ServiceA, instance0), (ServiceB, instance1), (ServiceA, instance2)]

        resolve_all(BaseService) needs global order to return [A0, B1, A2]
        Using just dict would give [A0, A2, B1] (grouped by type)

    Weak References:
    ================
    We do NOT use weak references because:
    - Providers are service containers that own their services
    - Services disappearing unexpectedly would break the contract
    - Users can clear() or not create a provider if they want GC
    - Strong references are the correct semantic for a DI container
"""

from collections.abc import Sequence
from typing import Any, Protocol, TypeVar, cast

ServiceT = TypeVar("ServiceT")


class ServiceNotFoundError(Exception):
    """Raised when a requested service type is not registered.

    Attributes:
        service_type: The type that was requested but not found.
        available_types: List of all registered service types.
    """

    def __init__(self, service_type: type, available_types: list[type]) -> None:
        self.service_type = service_type
        self.available_types = available_types

        type_names = [t.__name__ for t in available_types]
        available_str = ", ".join(type_names) if type_names else "none"

        super().__init__(
            f"No service of type '{service_type.__name__}' is registered.\n"
            f"Available service types: {available_str}"
        )


class ServiceProvider(Protocol):
    """Protocol defining the interface for service resolution.

    This protocol allows for multiple implementations of service providers,
    enabling different resolution strategies while maintaining a consistent API.

    The ServiceProvider protocol is designed to be:
    - Read-only: No mutation methods (add, remove, etc.)
    - Thread-safe: All implementations should support concurrent reads
    - Deterministic: Same query always returns same results
    - Type-safe: Full generic type support

    Implementations must support:
    1. Exact type resolution (resolve)
    2. Inheritance-aware resolution (resolve_all)
    3. Type existence checks (has)
    4. Type introspection (get_all_types)

    Standard Implementation:
        The default implementation is _Provider, created by
        ServiceCollection.build_provider(). Users typically don't
        construct providers directly.

    Custom Implementations:
        Custom providers can be created for:
        - Lazy initialization of services
        - Factory-based service creation
        - Scoped lifetime management
        - Integration with other DI frameworks
        - Caching strategies
        - Conditional service resolution

    Example Custom Implementation:
        ```python
        class LazyServiceProvider:
            def __init__(self, factories: dict[type, Callable]):
                self._factories = factories
                self._instances: dict[type, Any] = {}

            def resolve[T](self, service_type: type[T]) -> T:
                if service_type not in self._instances:
                    factory = self._factories[service_type]
                    self._instances[service_type] = factory()
                return self._instances[service_type]

            def resolve_all[T](self, service_type: type[T]) -> Sequence[T]:
                # Implementation...
                pass

            def has(self, service_type: type) -> bool:
                return service_type in self._factories

            def get_all_types(self) -> tuple[type, ...]:
                return tuple(self._factories.keys())
        ```

    Thread Safety Requirements:
        Implementations MUST be thread-safe for all read operations:
        - Multiple threads can call resolve() concurrently
        - Multiple threads can call resolve_all() concurrently
        - Multiple threads can call has() concurrently
        - Multiple threads can call get_all_types() concurrently

        Implementations do NOT need write operations (no add/remove),
        so thread safety is achieved through immutability.

    Type Resolution Semantics:
        - resolve(): MUST use exact type matching only
          - resolve(BaseClass) raises if only SubClass is registered
          - Returns first registered instance of exact type
          - Raises ServiceNotFoundError if type not found

        - resolve_all(): MUST support inheritance
          - resolve_all(BaseClass) returns all SubClass instances
          - Returns instances in registration order
          - Returns empty sequence if no matches (does NOT raise)
          - Uses isinstance() for type checking

        - has(): MUST use exact type matching only
          - has(BaseClass) returns False if only SubClass is registered
          - Checks for exact type, not inheritance

    Registration Order:
        Implementations MUST preserve registration order when:
        - Returning multiple instances of same type
        - Returning instances across inheritance hierarchy
        - The order is the global registration order, not per-type

    See Also:
        - ServiceCollection: Builder for registering services
        - _Provider: Default immutable implementation
        - resolve(): Get single instance by exact type
        - resolve_all(): Get all instances with inheritance
    """

    def resolve(self, service_type: type[ServiceT]) -> ServiceT:
        """Resolve the first registered instance of the exact type.

        This method performs EXACT type matching only. It will NOT return
        instances of subclasses. For inheritance-aware resolution, use
        resolve_all().

        Args:
            service_type: The exact type of service to resolve.

        Returns:
            The first registered instance of the exact type.

        Raises:
            ServiceNotFoundError: If no instance of the exact type is registered.
                The error includes the requested type and a list of available types.

        Example:
            ```python
            # Exact type matching
            service = provider.resolve(ConcreteService)  # Returns ConcreteService

            # Does NOT match subclasses
            provider.resolve(BaseService)  # Raises if only ConcreteService registered
            ```

        Thread Safety:
            This method MUST be thread-safe. Multiple threads can call it
            concurrently.

        Performance:
            Implementations SHOULD provide O(1) lookup for exact type matching.

        See Also:
            - resolve_all(): For inheritance-aware resolution
            - has(): To check before resolving
        """
        ...

    def resolve_all(self, service_type: type[ServiceT]) -> Sequence[ServiceT]:
        """Resolve all instances of the type, including subclasses.

        This method performs INHERITANCE-AWARE resolution. It returns all
        registered instances that are instances of the given type, including
        subclasses and implementations.

        The returned instances MUST be in registration order (the global
        order across all types, not grouped by type).

        Args:
            service_type: The type (or base type) of services to resolve.
                Can be a class, abstract class, or protocol.

        Returns:
            A sequence of all matching instances in registration order.
            Returns empty sequence if no instances match.
            MUST return an immutable sequence (tuple or similar).

        Example:
            ```python
            class Base: pass
            class ConcreteA(Base): pass
            class ConcreteB(Base): pass

            # Register: A1, B1, A2
            services.add(ConcreteA())  # A1
            services.add(ConcreteB())  # B1
            services.add(ConcreteA())  # A2

            # Resolve all Base instances (includes subclasses)
            all_base = provider.resolve_all(Base)
            # Returns [A1, B1, A2] in registration order

            # Resolve specific subclass
            all_a = provider.resolve_all(ConcreteA)
            # Returns [A1, A2]
            ```

        Inheritance Matching:
            Implementations MUST use isinstance() or equivalent for matching.
            This ensures proper support for:
            - Single inheritance
            - Multiple inheritance
            - Abstract base classes
            - Protocols (runtime checkable)
            - Mixins

        Registration Order:
            The returned sequence MUST preserve GLOBAL registration order,
            not per-type order. If services were registered as [A, B, A],
            resolve_all(Base) must return [A, B, A], not [A, A, B].

        Empty Results:
            Unlike resolve(), this method does NOT raise an exception when
            no instances are found. It returns an empty sequence instead.
            Use has() if you need to distinguish "not registered" from
            "registered but empty".

        Thread Safety:
            This method MUST be thread-safe. Multiple threads can call it
            concurrently.

        Performance:
            Implementations MAY have O(n) complexity where n is total instances,
            as inheritance checking requires isinstance() on each instance.

        See Also:
            - resolve(): For exact type matching (no inheritance)
            - has(): To check exact type registration
        """
        ...

    def has(self, service_type: type) -> bool:
        """Check if any instances of the exact type are registered.

        This method performs EXACT type matching only. It does NOT check
        for subclasses.

        Args:
            service_type: The exact type to check for.

        Returns:
            True if at least one instance of the exact type is registered,
            False otherwise.

        Example:
            ```python
            class Base: pass
            class Concrete(Base): pass

            services.add(Concrete())
            provider = services.build_provider()

            provider.has(Concrete)  # True (exact match)
            provider.has(Base)      # False (no exact match)

            # To check if any subclasses exist:
            len(provider.resolve_all(Base)) > 0  # True
            ```

        Inheritance:
            This method does NOT check subclasses. To check if any instances
            matching a base type exist (including subclasses), use:
            `len(provider.resolve_all(BaseType)) > 0`

        Thread Safety:
            This method MUST be thread-safe. Multiple threads can call it
            concurrently.

        Performance:
            Implementations SHOULD provide O(1) lookup.

        See Also:
            - resolve(): To get the instance after checking
            - resolve_all(): For inheritance-aware existence checks
        """
        ...

    def get_all_types(self) -> tuple[type, ...]:
        """Get all registered service types (exact types only).

        Returns the set of all types that have at least one registered instance.
        Only exact types are returned (not base classes unless explicitly registered).

        Returns:
            Tuple of all registered service types. Order is not guaranteed.
            Returns empty tuple if no services are registered.

        Example:
            ```python
            services.add(ServiceA())
            services.add(ServiceB())
            services.add(ServiceA())  # Second instance

            provider = services.build_provider()
            types = provider.get_all_types()
            # Returns (ServiceA, ServiceB) - order not guaranteed

            # Can iterate over all registered types
            for service_type in provider.get_all_types():
                instances = provider.resolve_all(service_type)
                print(f"{service_type.__name__}: {len(instances)} instance(s)")
            ```

        Use Cases:
            - Service discovery: Find all available service types
            - Debugging: Inspect what's registered
            - Validation: Verify expected services are present
            - Introspection: Build dynamic behaviors based on services

        Order:
            The order of types in the returned tuple is NOT guaranteed.
            Different implementations may return types in different orders.
            Do not rely on ordering.

        Thread Safety:
            This method MUST be thread-safe. Multiple threads can call it
            concurrently.

        Performance:
            Implementations SHOULD provide O(1) or O(k) where k is number
            of unique types (typically small).

        See Also:
            - has(): To check for specific type
            - resolve_all(): To get instances of a type
        """
        ...


class ServiceCollection:
    """Mutable collection for registering service instances.

    ServiceCollection is a builder for service registrations. Services are stored
    by their concrete type, and multiple instances of the same type can be registered.
    Registration order is preserved globally across all types.

    The collection is mutable and designed for the registration phase. Once all
    services are registered, call `build_provider()` to create an immutable
    ServiceProvider for resolution.

    Data Structure Rationale:
        Uses two complementary data structures:
        1. dict[type, list]: Fast O(1) exact type lookup
        2. list[tuple]: Preserve global registration order for inheritance

        See module docstring for detailed explanation of why both are needed.

    Thread Safety:
        ServiceCollection is NOT thread-safe. All registrations should happen
        in a single thread before calling build_provider().

    Attributes:
        _services: Internal storage mapping types to ordered lists of instances.
        _registration_order: Global registration order across all types.

    Example:
        ```python
        # Register services
        services = ServiceCollection()
        services.add(DatabaseService())
        services.add(EmailService())
        services.add(LoggerService())

        # Register multiple instances of same type
        services.add(CacheService(ttl=60))
        services.add(CacheService(ttl=300))

        # Build immutable provider
        provider = services.build_provider()
        ```

    See Also:
        - ServiceProvider: Protocol for service resolution
        - _Provider: Concrete immutable implementation
        - build_provider(): Create provider from collection
    """

    def __init__(self) -> None:
        """Initialize an empty service collection."""
        # Maps service type -> list of instances (maintains per-type registration order)
        # dict is ordered in Python 3.7+, but we track types, not instances
        self._services: dict[type, list[Any]] = {}

        # Global registration order: list of (type, instance) tuples
        # This is essential for resolve_all() to return instances in global order
        # when querying by base class (inheritance)
        self._registration_order: list[tuple[type, Any]] = []

    def add(self, instance: object) -> "ServiceCollection":
        """Register a service instance.

        Services are registered by their concrete type (type(instance)). Multiple
        instances of the same type can be registered and will be returned in
        registration order when resolved.

        Args:
            instance: The service instance to register. Cannot be None.

        Returns:
            Self for method chaining.

        Raises:
            ValueError: If instance is None.

        Example:
            ```python
            services = ServiceCollection()

            # Register single instance
            services.add(MyService())

            # Register multiple instances of same type
            services.add(CacheService(ttl=60))
            services.add(CacheService(ttl=300))

            # Method chaining
            services.add(ServiceA()).add(ServiceB()).add(ServiceC())

            # Same instance can be registered multiple times
            singleton = MyService()
            services.add(singleton)
            services.add(singleton)  # Registered twice
            ```

        Note:
            Services are registered by their concrete type, not by base classes.
            To resolve by base class, use ServiceProvider.resolve_all() which
            supports inheritance.
        """
        if instance is None:
            raise ValueError("Cannot register None as a service instance")

        service_type = type(instance)

        # Add to type-specific list
        if service_type not in self._services:
            self._services[service_type] = []
        self._services[service_type].append(instance)

        # Add to global registration order
        self._registration_order.append((service_type, instance))

        return self

    def build_provider(self) -> ServiceProvider:
        """Create an immutable ServiceProvider from this collection.

        Creates a ServiceProvider that contains a snapshot of all currently
        registered services. The provider is immutable and will not reflect
        any subsequent changes to the collection.

        This method can be called multiple times to create multiple independent
        providers from different collection states.

        Returns:
            A new immutable ServiceProvider instance (specifically _Provider).

        Example:
            ```python
            services = ServiceCollection()
            services.add(MyService())

            # Create provider
            provider = services.build_provider()

            # Provider is immutable - changes to collection don't affect it
            services.add(AnotherService())
            provider.has(AnotherService)  # False

            # Can create multiple providers
            provider2 = services.build_provider()
            provider2.has(AnotherService)  # True
            ```

        Implementation Note:
            Returns a _Provider instance that implements the ServiceProvider protocol.
            The concrete type is not part of the public API - users should type
            hint as ServiceProvider.

        See Also:
            - ServiceProvider: The protocol interface
            - _Provider: The concrete implementation (private)
        """
        return _Provider(self)

    def clear(self) -> None:
        """Remove all registered services from the collection.

        This completely clears the collection, removing all service registrations.
        Existing ServiceProviders created from this collection are not affected
        (they are immutable snapshots).

        Example:
            ```python
            services = ServiceCollection()
            services.add(MyService())

            provider1 = services.build_provider()
            services.clear()

            # provider1 still has MyService
            # but new providers won't
            provider2 = services.build_provider()
            ```
        """
        self._services.clear()
        self._registration_order.clear()

    def __len__(self) -> int:
        """Return the total number of registered service instances.

        Returns:
            Total count of all registered instances across all types.

        Example:
            ```python
            services = ServiceCollection()
            services.add(ServiceA())
            services.add(ServiceB())
            services.add(ServiceA())  # Second instance
            len(services)  # 3
            ```
        """
        return len(self._registration_order)

    def __repr__(self) -> str:
        """Return a developer-friendly representation of the collection."""
        type_counts = {t.__name__: len(instances) for t, instances in self._services.items()}
        return f"ServiceCollection(services={type_counts}, total={len(self)})"


class _Provider:
    """Immutable provider for resolving service instances (private implementation).

    This is the concrete implementation of the ServiceProvider protocol.
    Users should not construct this directly - use ServiceCollection.build_provider().

    _Provider is created from a ServiceCollection and provides read-only
    access to registered services. It supports:

    - Exact type matching (resolve)
    - Inheritance-based resolution (resolve_all)
    - Multiple instances per type (returned in registration order)
    - Type-safe resolution with generics

    The provider is immutable after creation and will not reflect any changes
    made to the original ServiceCollection.

    Thread Safety:
        _Provider is thread-safe for reading. Multiple threads can safely
        call resolve() concurrently. Immutability is enforced through:
        - Using tuples (immutable) instead of lists
        - Deep copying collection state at construction
        - No mutation methods

    Attributes:
        _services: Immutable snapshot of type -> instances mapping.
        _registration_order: Immutable snapshot of global registration order.

    See Also:
        - ServiceProvider: The protocol this implements
        - ServiceCollection: Mutable collection for registration
    """

    def __init__(self, collection: ServiceCollection) -> None:
        """Create an immutable provider from a service collection.

        This constructor is called by ServiceCollection.build_provider().
        Users should not call this directly.

        The provider takes a snapshot of the collection's state. Subsequent
        changes to the collection will not affect this provider.

        Args:
            collection: The ServiceCollection to create a provider from.
        """
        # Create immutable copies of the collection's internal state
        # This ensures the provider is truly immutable and won't be affected
        # by subsequent changes to the collection

        # Deep copy the services mapping, converting lists to tuples
        self._services: dict[type, tuple[Any, ...]] = {
            service_type: tuple(instances)
            for service_type, instances in collection._services.items()
        }

        # Copy the global registration order as a tuple (immutable)
        self._registration_order: tuple[tuple[type, Any], ...] = tuple(
            collection._registration_order
        )

    def resolve(self, service_type: type[ServiceT]) -> ServiceT:
        """Resolve the first registered instance of the given type.

        Returns the first instance registered for the exact type. This does NOT
        perform inheritance matching. If you need all instances including
        subclasses, use resolve_all().

        Args:
            service_type: The type of service to resolve.

        Returns:
            The first registered instance of the requested type.

        Raises:
            ServiceNotFoundError: If no instance of the requested type is registered.

        See Also:
            - resolve_all(): Get all instances including subclasses
            - has(): Check if type is registered before resolving
        """
        if service_type not in self._services:
            raise ServiceNotFoundError(service_type, list(self._services.keys()))

        # Return first instance of the exact type
        return cast(ServiceT, self._services[service_type][0])

    def resolve_all(self, service_type: type[ServiceT]) -> Sequence[ServiceT]:
        """Resolve all instances of the given type, including subclasses.

        Returns all registered instances that are instances of the given type,
        respecting the global registration order. This includes:

        - Exact type matches
        - Subclass instances (inheritance support)
        - Multiple instances per type

        The returned sequence preserves the order in which services were registered
        across ALL types.

        Args:
            service_type: The type (or base type) of services to resolve.

        Returns:
            A sequence of all matching instances in registration order.
            Returns empty tuple if no instances match.

        See Also:
            - resolve(): Get just the first instance
            - has(): Check if any instances are registered
        """
        # Filter registration order by isinstance check to support inheritance
        # This maintains global registration order while filtering by type
        matching_instances = tuple(
            instance
            for _, instance in self._registration_order
            if isinstance(instance, service_type)
        )

        return matching_instances

    def has(self, service_type: type) -> bool:
        """Check if any instances of the given type are registered.

        Checks for exact type match only (does not check subclasses).

        Args:
            service_type: The type to check for.

        Returns:
            True if at least one instance of the exact type is registered,
            False otherwise.

        Note:
            This only checks for exact type matches. To check if any subclasses
            are registered, use: `len(provider.resolve_all(BaseType)) > 0`
        """
        return service_type in self._services

    def get_all_types(self) -> tuple[type, ...]:
        """Get all registered service types.

        Returns the set of all types that have at least one registered instance.
        The order is not guaranteed.

        Returns:
            Tuple of all registered service types.
        """
        return tuple(self._services.keys())

    def __len__(self) -> int:
        """Return the total number of registered service instances.

        Returns:
            Total count of all registered instances across all types.
        """
        return len(self._registration_order)

    def __repr__(self) -> str:
        """Return a developer-friendly representation of the provider."""
        type_counts = {t.__name__: len(instances) for t, instances in self._services.items()}
        return f"ServiceProvider(services={type_counts}, total={len(self)})"
