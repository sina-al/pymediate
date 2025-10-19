"""Dependency Injector integration for PyMediate.

This module provides a resolver that integrates with the dependency-injector library,
allowing handlers to be resolved from a DI container using type inspection rather than
naming conventions.
"""

from typing import Any

from dependency_injector import containers

from pymediate.errors import DIContainerError, HandlerNotFoundError
from pymediate.handler import Handler


class DependencyInjectorResolver:
    """Resolver that uses a dependency-injector Container to resolve handlers.

    This resolver works WITHOUT naming conventions by using type inspection:
    - Scans all providers in the container at initialization
    - Identifies Handler instances by checking isinstance(obj, Handler)
    - Extracts the request type from Handler._request_type
    - Builds a direct mapping from request type to provider

    This means handler providers can have ANY name - no conventions required!

    Example:
        from dependency_injector import containers, providers

        class AppContainer(containers.DeclarativeContainer):
            database = providers.Singleton(Database)

            # Provider can have ANY name - no convention needed!
            user_creation_service = providers.Factory(
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

    Performance:
        First resolve: O(1) lookup from pre-built cache
        Subsequent resolves: O(1) lookup from cache
    """

    def __init__(self, container: containers.Container) -> None:
        """Initialize resolver with a dependency-injector container.

        Scans the container on initialization to build a cache mapping
        request types to their handler providers using type inspection.

        Args:
            container: Any dependency-injector Container instance
        """
        self._container = container
        # Maps request type -> provider that creates the handler
        self._handler_providers: dict[type, Any] = {}
        self._scan_container()

    def _scan_container(self) -> None:
        """Scan container for handler providers and build request type mapping.

        This runs once at initialization. For each provider in the container:
        1. Call the provider to get an instance
        2. Check if it's a Handler subclass using isinstance()
        3. Extract the request type from Handler._request_type
        4. Map request_type -> provider for O(1) lookups

        This approach works with ANY provider names - no conventions needed!
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
                    # Extract the request type from the Handler class
                    request_type = type(instance).get_request_type()

                    if request_type is not None:
                        # Map request type to provider
                        self._handler_providers[request_type] = provider

            except Exception:
                # If provider can't be instantiated yet (missing dependencies, etc.),
                # skip it silently. This is expected for some providers.
                pass

    def resolve(self, request_class: type) -> Any:
        """Resolve a handler instance for the given request type.

        Uses type-based lookup - NO naming conventions required!

        Args:
            request_class: The request class to resolve a handler for

        Returns:
            The handler instance from the container

        Raises:
            ValueError: If no handler is found for the request type
        """
        # O(1) lookup from pre-built type-based cache
        if request_class not in self._handler_providers:
            available = list(self._handler_providers.keys())
            raise HandlerNotFoundError(request_class, available)

        # Get the provider and call it to get a handler instance
        try:
            provider = self._handler_providers[request_class]
            return provider()
        except Exception as e:
            raise DIContainerError(
                request_class, f"Container failed to provide handler: {e}"
            ) from e
