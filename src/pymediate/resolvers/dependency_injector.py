"""Dependency Injector integration for PyMediate.

This module provides a resolver that integrates with the dependency-injector library,
allowing handlers to be resolved from a DI container using type inspection.
"""

from typing import Any, cast

from dependency_injector import containers

from .. import errors
from ..handler import Handler


class DependencyInjectorResolver:
    """Resolver that integrates with dependency-injector library.

    This resolver uses type inspection to automatically discover handlers from a
    dependency-injector Container. It scans all providers in the container at
    initialization and builds a mapping from handler types to their providers.

    The resolver is responsible solely for instantiating handler instances from
    handler types. The mediator handles request-to-handler-type mapping via the
    registry.

    Attributes:
        _container: The dependency-injector Container instance.
        _handler_providers: Dict mapping handler types to their providers.

    Examples:
        Basic setup with Factory providers:
            ```python
            from dependency_injector import containers, providers

            class AppContainer(containers.DeclarativeContainer):
                database = providers.Singleton(Database)

                # Handler providers - type inspection finds them automatically!
                create_user_handler = providers.Factory(
                    CreateUserHandler,
                    database=database
                )

                __self__ = providers.Self()
                mediator = providers.Singleton(
                    Mediator,
                    resolver=providers.Singleton(
                        DependencyInjectorResolver,
                        container=__self__
                    )
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
                resolver = providers.Singleton(
                    DependencyInjectorResolver,
                    container=__self__
                )
            ```

    Performance:
        - Initialization: O(n) where n is number of providers (one-time cost)
        - Resolution: O(1) lookup from pre-built cache
        - Subsequent resolves: O(1) lookup from cache

    Note:
        The container is scanned once at initialization. If you add providers
        after creating the resolver, you'll need to create a new resolver instance.

    See Also:
        - Resolver: The protocol this class implements
        - SimpleResolver: Simpler dict-based alternative
    """

    def __init__(self, container: containers.Container) -> None:
        """Initialize resolver with a dependency-injector container.

        Scans the container immediately to build a cache mapping handler types
        to their providers using type inspection. This enables O(1) lookups.

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
            resolver = DependencyInjectorResolver(container)
            ```

        Note:
            The container scan happens in __init__, so any handlers added after
            initialization won't be discovered.
        """
        self._container = container
        # Maps handler type -> provider that creates the handler
        self._handler_providers: dict[type[Handler[Any]], Any] = {}
        self._scan_container()

    def _scan_container(self) -> None:
        """Scan container for handler providers and build handler type mapping.

        This runs once at initialization. For each provider in the container:
        1. Call the provider to get an instance
        2. Check if it's a Handler subclass using isinstance()
        3. Extract the handler type from type(instance)
        4. Map handler_type -> provider for O(1) lookups

        Note:
            Providers that can't be instantiated (e.g., missing dependencies) are
            silently skipped. This is expected behavior during container scanning.
        """
        if not hasattr(self._container, "providers"):
            return

        for _provider_name, provider in self._container.providers.items():
            try:
                # Try to get an instance from the provider
                # For Factory providers, this creates a new instance
                # For Singleton providers, this gets the singleton
                instance = provider()

                # Check if it's a Handler subclass
                if isinstance(instance, Handler):
                    # Extract the handler type
                    handler_type = type(instance)
                    # Map handler type to provider
                    self._handler_providers[handler_type] = provider

            except Exception:
                # If provider can't be instantiated yet (missing dependencies, etc.),
                # skip it silently. This is expected for some providers.
                pass

    def resolve(self, handler_class: type[Handler[Any]]) -> Handler[Any]:
        """Resolve a handler instance for the given handler type.

        Uses type-based lookup from the pre-built cache. Simply calls the
        appropriate provider to get a handler instance.

        Args:
            handler_class: The handler class to resolve.

        Returns:
            The handler instance from the container. Whether you get a new instance
            or a singleton depends on the provider type (Factory vs Singleton).

        Raises:
            HandlerNotFoundError: If no handler is found for the handler type.
                The error includes a list of available handlers.
            DIContainerError: If the container fails to provide the handler instance
                (e.g., due to missing dependencies).

        Examples:
            ```python
            resolver = DependencyInjectorResolver(container)

            # Resolves CreateUserHandler from container (called by mediator)
            handler = resolver.resolve(CreateUserHandler)
            response = handler(CreateUserRequest(username="alice"))
            ```

        Note:
            Each call to resolve() invokes the provider. For Factory providers,
            this creates a new handler instance. For Singleton providers, the
            same instance is returned.
        """
        # O(1) lookup from pre-built type-based cache
        if handler_class not in self._handler_providers:
            available = list(self._handler_providers.keys())
            raise errors.HandlerNotFoundError(handler_class, available)

        # Get the provider and call it to get a handler instance
        try:
            provider = self._handler_providers[handler_class]
            return cast(Handler[Any], provider())
        except Exception as e:
            raise errors.DIContainerError(
                handler_class, f"Container failed to provide handler: {e}"
            ) from e
