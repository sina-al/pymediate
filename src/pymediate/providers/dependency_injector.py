"""Dependency Injector integration for PyMediate ServiceProvider.

This module provides a ServiceProvider that integrates with the dependency-injector
library, allowing services (including handlers) to be resolved from a DI container.
"""

from collections.abc import Callable, Mapping, Sequence
from typing import Any, Protocol

from ..service import ServiceNotFoundError


class ContainerLike(Protocol):
    """Structural type for dependency-injector containers.

    Matches any object that exposes a ``providers`` mapping of provider
    callables. Every dependency-injector container (`DeclarativeContainer`,
    `DynamicContainer`) satisfies it, so you never implement this protocol
    yourself - pass your container instance where a `ContainerLike` is expected.
    """

    @property
    def providers(self) -> Mapping[str, Callable[[], Any]]:
        """Mapping of provider name to provider callable."""
        ...


class DependencyInjectorServiceProvider:
    """ServiceProvider backed by a dependency-injector container.

    Scans every provider in the container once, at construction time, building a
    type-keyed cache for O(1) lookups. Works with any provider type - `Factory`,
    `Singleton`, and so on - since it only cares about the type of instance each
    provider produces, not how that provider manages the instance's lifetime.

    Build it from a container you've already constructed - not from a provider
    declared inside that same container, which would require the container to
    resolve this provider while still scanning itself.

    Examples:
        ```python
        from dependency_injector import containers, providers
        from pymediate import Mediator
        from pymediate.providers import DependencyInjectorServiceProvider

        class AppContainer(containers.DeclarativeContainer):
            database = providers.Singleton(Database)
            create_user_handler = providers.Factory(CreateUserHandler, database=database)

        container = AppContainer()
        provider = DependencyInjectorServiceProvider(container)
        mediator = Mediator(provider)

        response = mediator.send(CreateUserRequest(...))
        ```

    Note:
        The container is scanned once, in `__init__`. Providers added to the
        container afterward won't be picked up - construct a new
        `DependencyInjectorServiceProvider` instead.

    See Also:
        - ServiceProvider: The protocol this class implements.
        - Services: A DI-container-free alternative for manual service registration.
    """

    def __init__(self, container: ContainerLike) -> None:
        """Scan a dependency-injector container and cache its providers by type.

        Args:
            container: Any dependency-injector Container instance
                (`DeclarativeContainer` or `DynamicContainer`).
        """
        self._container = container
        self._type_providers: dict[type, list[Any]] = {}
        self._registration_order: list[tuple[type, Any]] = []
        self._scan_container()

    def _scan_container(self) -> None:
        """Call every provider once to learn its instance type, then index by type."""
        if not hasattr(self._container, "providers"):
            return

        for _provider_name, provider in self._container.providers.items():
            instance = provider()
            service_type = type(instance)

            if service_type not in self._type_providers:
                self._type_providers[service_type] = []
            self._type_providers[service_type].append(provider)

            self._registration_order.append((service_type, provider))

    def get(self, service_type: type[Any]) -> Any:
        """Get the first registered instance of the exact type.

        Args:
            service_type: The exact type of service to get.

        Returns:
            The first registered instance of the exact type.

        Raises:
            ServiceNotFoundError: If no instance of the exact type is registered.
        """
        if service_type not in self._type_providers:
            available = list(self._type_providers.keys())
            raise ServiceNotFoundError(service_type, available)

        providers_list = self._type_providers[service_type]
        return providers_list[0]()

    def get_all(self, service_type: type[Any]) -> Sequence[Any]:
        """Get all instances of the type, including subclasses, in registration order.

        Args:
            service_type: The type (or base type) of services to resolve.

        Returns:
            All matching instances in registration order, or an empty sequence.
        """
        result: list[Any] = []
        for _reg_type, provider in self._registration_order:
            instance = provider()
            if isinstance(instance, service_type):
                result.append(instance)
        return result

    def has(self, service_type: type) -> bool:
        """Check whether any instance of the exact type is registered.

        Args:
            service_type: The type to check for.

        Returns:
            True if at least one instance of the exact type is registered.
        """
        return service_type in self._type_providers

    def get_all_types(self) -> tuple[type, ...]:
        """Get every exact type that has at least one registered instance.

        Returns:
            All registered service types, in no particular order.
        """
        return tuple(self._type_providers.keys())

    def __len__(self) -> int:
        """Return the total number of registered service instances."""
        return len(self._registration_order)
