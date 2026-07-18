"""Service collection and provider for dependency injection.

Register service instances with ``Services``, then build an immutable ``ServiceProvider``
from it to resolve them. Multiple instances of the same type can be registered, and
``get_all()`` resolves by inheritance, so a base type or runtime-checkable protocol
matches registered instances that satisfy it.

Examples:
    ```python
    from pymediate import Services

    class Cache:
        pass

    cache = Cache()
    services = Services().add(cache)

    provider = services.provider()

    assert provider.get(Cache) is cache
    assert provider.get_all(Cache) == (cache,)
    ```
"""

from collections.abc import Sequence
from typing import Any, Protocol, TypeVar, cast

ServiceT = TypeVar("ServiceT")


class ServiceNotFoundError(Exception):
    """Raised when a requested service type is not registered.

    Attributes:
        service_type: The type that was requested but not found.
        available_types: All registered service types.
    """

    def __init__(self, service_type: type, available_types: list[type]) -> None:
        """Create the error for a service type that has no registered instance.

        Args:
            service_type: The type that was requested but not found.
            available_types: All registered service types, for the error message.
        """
        self.service_type = service_type
        self.available_types = available_types

        type_names = [t.__name__ for t in available_types]
        available_str = ", ".join(type_names) if type_names else "none"

        super().__init__(
            f"No service of type '{service_type.__name__}' is registered.\n"
            f"Available service types: {available_str}"
        )


class ServiceProvider(Protocol):
    """Protocol for resolving registered service instances.

    ``get()`` matches an exact registered type. ``get_all()`` also matches
    subclasses and runtime-checkable protocols, returning all matches in
    registration order.

    ``Services.provider()`` returns the built-in implementation.
    ``DependencyInjectorServiceProvider`` adapts a Dependency Injector container.
    A custom provider can use another resolution and lifetime policy while
    implementing the same five operations.

    Note:
        The protocol is read-only. Thread-safety and mutation behavior depend on
        the implementation.
    """

    def get(self, service_type: type[ServiceT]) -> ServiceT:
        """Get the first registered instance of the exact type.

        Uses exact type matching only - a request for a base class doesn't match a
        registered subclass. Use `get_all()` for inheritance-aware resolution.

        Args:
            service_type: The exact type of service to get.

        Returns:
            The first registered instance of the exact type.

        Raises:
            ServiceNotFoundError: If no instance of the exact type is registered.
        """
        ...

    def get_all(self, service_type: type[ServiceT]) -> Sequence[ServiceT]:
        """Get all instances of the type, including subclasses.

        Matches using ``isinstance()``, so a base class, abstract class, or
        runtime-checkable protocol resolves registered instances that satisfy it.

        Args:
            service_type: The type (or base type) of services to resolve.

        Returns:
            All matching instances, in registration order. Empty if none match -
            unlike `get()`, this never raises for zero results.
        """
        ...

    def has(self, service_type: type) -> bool:
        """Check whether any instance of the exact type is registered.

        Like `get()`, this uses exact type matching only. To check for subclasses
        too, use `len(provider.get_all(base_type)) > 0` instead.

        Args:
            service_type: The exact type to check for.

        Returns:
            True if at least one instance of the exact type is registered.
        """
        ...

    def get_all_types(self) -> tuple[type, ...]:
        """Get every exact type that has at least one registered instance.

        Returns:
            All registered service types, in no particular order.
        """
        ...

    def __len__(self) -> int:
        """Return how many service instances are registered in total.

        Returns:
            The total instance count across all types. An instance registered
            twice counts twice.
        """
        ...


class Services:
    """Mutable collection for registering service instances.

    Register instances with `add()`, then call `provider()` once registration is
    complete to get an immutable `ServiceProvider` for resolution. Registering more
    instances after calling `provider()` doesn't affect providers already created -
    each one is a snapshot.

    Not thread-safe: complete all registrations in a single thread before calling
    `provider()`.

    """

    def __init__(self) -> None:
        """Create an empty service collection."""
        # Maps each concrete type to its registered instances, in registration order.
        self._services: dict[type, list[Any]] = {}

        # Global registration order across all types - needed because get_all() must
        # return instances in the order they were registered overall, not grouped by
        # type (e.g. [A, B, A] registered in that order must resolve as [A, B, A] for
        # a shared base type, not [A, A, B]).
        self._registration_order: list[tuple[type, Any]] = []

    def add(self, instance: object) -> "Services":
        """Register a service instance.

        Instances are registered by their concrete type (`type(instance)`). Multiple
        instances of the same type - including the same instance registered more than
        once - are all kept and returned in registration order when resolved.

        Args:
            instance: The service instance to register. Cannot be None.

        Returns:
            Self, so calls can be chained: `services.add(a).add(b)`.

        Raises:
            ValueError: If instance is None.

        """
        if instance is None:
            raise ValueError("Cannot register None as a service instance")

        service_type = type(instance)

        if service_type not in self._services:
            self._services[service_type] = []
        self._services[service_type].append(instance)

        self._registration_order.append((service_type, instance))

        return self

    def provider(self) -> ServiceProvider:
        """Build an immutable ServiceProvider from the currently registered services.

        The returned provider is a snapshot - later calls to `add()` or `clear()` on
        this collection don't affect providers already created. Call `provider()`
        again to get a fresh one reflecting the current state.

        Returns:
            A new ServiceProvider over the services registered so far.

        """
        return _Provider(self)

    def clear(self) -> None:
        """Remove all registered services from this collection.

        Providers already created via `provider()` are unaffected - they're
        immutable snapshots.
        """
        self._services.clear()
        self._registration_order.clear()

    def __len__(self) -> int:
        """Return the total number of registered service instances.

        Counts every registration, including a type or instance registered more
        than once - not the number of unique types.
        """
        return len(self._registration_order)

    def __repr__(self) -> str:
        """Return a developer-friendly representation of the collection."""
        type_counts = {t.__name__: len(instances) for t, instances in self._services.items()}
        return f"Services(services={type_counts}, total={len(self)})"


class _Provider:
    """Immutable ServiceProvider implementation returned by Services.provider().

    Takes a snapshot of a Services collection's registrations at construction time;
    later changes to that collection don't affect an existing _Provider instance.
    """

    def __init__(self, collection: Services) -> None:
        """Snapshot a Services collection's current registrations.

        Args:
            collection: The Services to build a provider from.
        """
        self._services: dict[type, tuple[Any, ...]] = {
            service_type: tuple(instances)
            for service_type, instances in collection._services.items()
        }
        self._registration_order: tuple[tuple[type, Any], ...] = tuple(
            collection._registration_order
        )
        # get_all() results per requested type. The provider is an immutable
        # snapshot, so entries can never go stale.
        self._get_all_cache: dict[type, tuple[Any, ...]] = {}

    def get(self, service_type: type[ServiceT]) -> ServiceT:
        """Get the first registered instance of the exact type.

        Args:
            service_type: The type of service to get.

        Returns:
            The first registered instance of the requested type.

        Raises:
            ServiceNotFoundError: If no instance of the requested type is registered.
        """
        if service_type not in self._services:
            raise ServiceNotFoundError(service_type, list(self._services.keys()))

        return cast(ServiceT, self._services[service_type][0])

    def get_all(self, service_type: type[ServiceT]) -> Sequence[ServiceT]:
        """Get all instances of the type, including subclasses, in registration order.

        The result is computed once per requested type and cached - the provider
        is an immutable snapshot, so repeated calls are a dict lookup.

        Args:
            service_type: The type (or base type) of services to resolve.

        Returns:
            All matching instances in registration order, or an empty tuple.
        """
        cached = self._get_all_cache.get(service_type)
        if cached is None:
            cached = tuple(
                instance
                for _, instance in self._registration_order
                if isinstance(instance, service_type)
            )
            self._get_all_cache[service_type] = cached
        return cached

    def has(self, service_type: type) -> bool:
        """Check whether any instance of the exact type is registered.

        Args:
            service_type: The type to check for.

        Returns:
            True if at least one instance of the exact type is registered.
        """
        return service_type in self._services

    def get_all_types(self) -> tuple[type, ...]:
        """Get every exact type that has at least one registered instance.

        Returns:
            All registered service types, in no particular order.
        """
        return tuple(self._services.keys())

    def __len__(self) -> int:
        """Return the total number of registered service instances."""
        return len(self._registration_order)

    def __repr__(self) -> str:
        """Return a developer-friendly representation of the provider."""
        type_counts = {t.__name__: len(instances) for t, instances in self._services.items()}
        return f"ServiceProvider(services={type_counts}, total={len(self)})"
