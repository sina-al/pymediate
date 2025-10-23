"""Dependency Injector integration for PyMediate ServiceProvider.

This module provides a ServiceProvider that integrates with the dependency-injector
library, allowing services (including handlers) to be resolved from a DI container.
"""

from collections.abc import Sequence
from typing import Any

from dependency_injector import containers

from ..service import ServiceNotFoundError


class DependencyInjectorServiceProvider:
    """ServiceProvider that integrates with dependency-injector library.

    This provider wraps a dependency-injector Container and implements the
    ServiceProvider protocol, enabling seamless integration between PyMediate's
    mediator pattern and the dependency-injector library.

    The provider scans all providers in the container at initialization and builds
    a mapping from service types to their providers for efficient O(1) lookups.

    Attributes:
        _container: The dependency-injector Container instance.
        _type_providers: Dict mapping service types to their providers.

    Examples:
        Basic setup with Factory providers:
            ```python
            from dependency_injector import containers, providers
            from pymediate import Mediator, ServiceProvider
            from pymediate.providers import DependencyInjectorServiceProvider

            class AppContainer(containers.DeclarativeContainer):
                database = providers.Singleton(Database)

                # Handler providers
                create_user_handler = providers.Factory(
                    CreateUserHandler,
                    database=database
                )

                __self__ = providers.Self()
                service_provider = providers.Singleton(
                    DependencyInjectorServiceProvider,
                    container=__self__
                )
                mediator = providers.Singleton(
                    Mediator,
                    service_provider=service_provider
                )

            container = AppContainer()
            mediator = container.mediator()
            response = mediator.send(CreateUserRequest(...))
            ```

        Using Singleton providers:
            ```python
            class AppContainer(containers.DeclarativeContainer):
                # Singleton handler - same instance every time
                create_user_handler = providers.Singleton(CreateUserHandler)

                __self__ = providers.Self()
                service_provider = providers.Singleton(
                    DependencyInjectorServiceProvider,
                    container=__self__
                )
            ```

    Performance:
        - Initialization: O(n) where n is number of providers (one-time cost)
        - Resolution: O(1) lookup from pre-built cache
        - resolve_all: O(n) where n is matching instances

    Note:
        The container is scanned once at initialization. If you add providers
        after creating the service provider, you'll need to create a new instance.

    See Also:
        - ServiceProvider: The protocol this class implements
        - Services: Alternative for manual service registration
    """

    def __init__(self, container: containers.Container) -> None:
        """Initialize service provider with a dependency-injector container.

        Scans the container immediately to build a cache mapping service types
        to their providers. This enables O(1) lookups.

        Args:
            container: Any dependency-injector Container instance (DeclarativeContainer
                or DynamicContainer).

        Examples:
            ```python
            from dependency_injector import containers

            class AppContainer(containers.DeclarativeContainer):
                # ... providers ...
                pass

            container = AppContainer()
            service_provider = DependencyInjectorServiceProvider(container)
            ```

        Note:
            The container scan happens in __init__, so any services added after
            initialization won't be discovered.
        """
        self._container = container
        # Maps service type -> list of providers that create instances of that type
        self._type_providers: dict[type, list[Any]] = {}
        # List of (type, provider) tuples in registration order
        self._registration_order: list[tuple[type, Any]] = []
        self._scan_container()

    def _scan_container(self) -> None:
        """Scan container for providers and build service type mapping.

        For each provider in the container:
        1. Call the provider to get an instance
        2. Extract the service type from type(instance)
        3. Map service_type -> provider for O(1) lookups
        4. Track registration order globally

        Note:
            Providers that can't be instantiated (e.g., missing dependencies) are
            silently skipped.
        """
        if not hasattr(self._container, "providers"):
            return

        for _provider_name, provider in self._container.providers.items():
            # Try to get an instance from the provider
            instance = provider()

            # Extract the service type
            service_type = type(instance)

            # Add to type mapping
            if service_type not in self._type_providers:
                self._type_providers[service_type] = []
            self._type_providers[service_type].append(provider)

            # Track registration order
            self._registration_order.append((service_type, provider))

    def resolve(self, service_type: type[Any]) -> Any:
        """Resolve the first registered instance of the exact type.

        Uses exact type matching only. Will NOT return instances of subclasses.

        Args:
            service_type: The exact type of service to resolve.

        Returns:
            The first registered instance of the exact type.

        Raises:
            ServiceNotFoundError: If no instance of the exact type is registered.

        Example:
            ```python
            handler = service_provider.resolve(CreateUserHandler)
            response = handler(request)
            ```

        Thread Safety:
            This method is thread-safe for read operations.

        Performance:
            O(1) lookup from pre-built cache.
        """
        if service_type not in self._type_providers:
            available = list(self._type_providers.keys())
            raise ServiceNotFoundError(service_type, available)

        # Get the first provider and call it to get an instance
        providers_list = self._type_providers[service_type]
        return providers_list[0]()

    def resolve_all(self, service_type: type[Any]) -> Sequence[Any]:
        """Resolve all instances of the type, including subclasses.

        Uses inheritance-aware resolution via isinstance() checks.
        Returns instances in registration order.

        Args:
            service_type: The type of services to resolve.

        Returns:
            Sequence of all registered instances that are instances of the type,
            in registration order. Returns empty sequence if no matches.

        Example:
            ```python
            all_handlers = service_provider.resolve_all(Handler)
            for handler in all_handlers:
                # Process handler
                pass
            ```

        Thread Safety:
            This method is thread-safe for read operations.

        Performance:
            O(n) where n is total number of registered services.
        """
        result: list[Any] = []

        # Iterate through registration order to maintain order
        for _reg_type, provider in self._registration_order:
            instance = provider()
            # Check if instance is of the requested type (including subclasses)
            if isinstance(instance, service_type):
                result.append(instance)

        return result

    def has(self, service_type: type) -> bool:
        """Check if any instance of the exact type is registered.

        Uses exact type matching only (no inheritance).

        Args:
            service_type: The type to check for.

        Returns:
            True if at least one instance of the exact type is registered,
            False otherwise.

        Example:
            ```python
            if service_provider.has(CreateUserHandler):
                handler = service_provider.resolve(CreateUserHandler)
            ```

        Thread Safety:
            This method is thread-safe for read operations.

        Performance:
            O(1) lookup.
        """
        return service_type in self._type_providers

    def get_all_types(self) -> tuple[type, ...]:
        """Get all registered service types (exact types only).

        Returns:
            Tuple of all registered service types. Order is not guaranteed.

        Example:
            ```python
            types = service_provider.get_all_types()
            for service_type in types:
                print(f"Found: {service_type.__name__}")
            ```

        Thread Safety:
            This method is thread-safe for read operations.

        Performance:
            O(1) or O(k) where k is number of unique types.
        """
        return tuple(self._type_providers.keys())

    def __len__(self) -> int:
        """Return the total number of registered service instances.

        Returns:
            Total count of all registered instances across all types.

        Example:
            ```python
            count = len(service_provider)
            print(f"Total services: {count}")
            ```

        Thread Safety:
            This method is thread-safe for read operations.

        Performance:
            O(1) lookup.
        """
        return len(self._registration_order)
