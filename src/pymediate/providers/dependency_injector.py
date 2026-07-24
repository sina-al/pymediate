"""Dependency Injector integration for PyMediate service resolution."""

from collections import defaultdict
from collections.abc import Callable
from inspect import Signature, isawaitable, iscoroutine, signature
from types import NoneType, UnionType
from typing import Annotated, Any, cast, get_args, get_origin, get_type_hints

from dependency_injector import containers, providers

from ..service import ServiceNotFoundError, ServiceProvider

type _Provider = providers.Provider[Any]


class DependencyInjectorServiceProvider(ServiceProvider):
    """ServiceProvider backed by a Dependency Injector container.

    Indexes services from the container without resolving them, then delegates each
    service resolution to its original Dependency Injector provider. Class-backed
    factories and singletons, object providers, and factories with concrete return
    annotations are discovered automatically.

    The whole provider graph is walked with ``Container.traverse()`` - nested
    ``providers.Container`` children and providers reachable only through injection
    are all visited. A provider whose output type cannot be inferred without resolving
    it (an unannotated factory, ``Selector``, ``Resource``, or coroutine provider) is
    skipped, not indexed, so infrastructure providers do not have to be
    PyMediate-resolvable. ``provider[Type]`` returns the first provider found for an
    exact type.

    Examples:
        ```python
        from dependency_injector import containers, providers
        from pymediate import Mediator
        from pymediate.providers import DependencyInjectorServiceProvider

        class Database:
            pass

        class PlaceOrderHandler:
            def __init__(self, database: Database) -> None:
                self.database = database

        class AppContainer(containers.DeclarativeContainer):
            database = providers.Singleton(Database)
            place_order = providers.Factory(PlaceOrderHandler, database=database)

        container = AppContainer()
        services = DependencyInjectorServiceProvider(container)
        mediator = Mediator(services=services)
        ```

    Note:
        The provider graph and inferred types are a construction-time snapshot.
        Rebuild this service provider after adding providers or applying an override
        that changes a provider's output type. Overrides that preserve the output type
        continue to work because service resolution remains delegated to the original
        Dependency Injector provider.

    """

    def __init__(self, container: containers.Container) -> None:
        """Index services declared by a Dependency Injector container.

        Args:
            container: A ``DeclarativeContainer`` or ``DynamicContainer`` instance.

        Raises:
            TypeError: If ``container`` is not a Dependency Injector container.
        """
        if not isinstance(container, containers.Container):
            raise TypeError("container must be a dependency_injector.containers.Container")

        self._container = container
        self._type_providers: defaultdict[type[Any], list[_Provider]] = defaultdict(list)

        # traverse() walks the whole provider graph - nested containers, and providers
        # reachable only through injection - and is cycle-safe, so no manual recursion
        # or cycle guarding is needed. An overridden provider resolves through the
        # override, so index by the effective (last_overriding) type.
        provider: _Provider
        for provider in container.traverse():
            effective: _Provider = provider.last_overriding or provider
            service_type = self._service_type(provider, effective)
            if service_type is not None:
                self._type_providers[service_type].append(provider)

    def _service_type(self, provider: _Provider, effective: _Provider) -> type[Any] | None:
        # Composition-only providers, and providers whose output type can't be inferred
        # without resolving them, are skipped - they never become services.
        if isinstance(
            provider,
            (
                providers.Configuration,
                providers.DependenciesContainer,
                providers.Dependency,
                providers.Self,
            ),
        ):
            return None

        if isinstance(effective, providers.Object):
            return type(effective.provides)

        if isinstance(effective, providers.List):
            return list

        if isinstance(effective, providers.Dict):
            return dict

        if isinstance(
            effective,
            (providers.Container, providers.Coroutine, providers.BaseResource),
        ):
            return None

        if isinstance(
            effective,
            (providers.Factory, providers.BaseSingleton, providers.Callable),
        ):
            return _callable_return_type(effective.provides)

        return None

    def _resolve(self, service_type: type[Any], provider: _Provider) -> Any:
        instance = provider()
        if isawaitable(instance):
            if iscoroutine(instance):
                instance.close()
            cancel = getattr(instance, "cancel", None)
            if callable(cancel):
                cancel()
            raise TypeError(
                f"provider '{_provider_label(provider)}' resolved asynchronously; "
                "PyMediate service providers must construct services synchronously"
            )
        if not isinstance(instance, service_type):
            raise TypeError(
                f"provider '{_provider_label(provider)}' produced {type(instance).__name__}, "
                f"not its indexed service type {service_type.__name__}; rebuild the "
                "DependencyInjectorServiceProvider after a type-changing override"
            )
        return instance

    def __getitem__[ServiceT](self, service_type: type[ServiceT]) -> ServiceT:
        """Get the first registered instance of the exact type.

        Args:
            service_type: The exact type of service to get.

        Returns:
            The first registered instance of the exact type.

        Raises:
            ServiceNotFoundError: If no instance of the exact type is registered.
            TypeError: If the matching provider resolves asynchronously or returns
                a value that does not match its indexed service type.
        """
        matches = self._type_providers.get(service_type)
        if not matches:
            raise ServiceNotFoundError(service_type, list(self._type_providers))
        return cast(ServiceT, self._resolve(service_type, matches[0]))

    def __contains__(self, service_type: type[Any]) -> bool:
        """Check whether any instance of the exact type is registered.

        Args:
            service_type: The type to check for.

        Returns:
            True if at least one instance of the exact type is registered.
        """
        return service_type in self._type_providers

    def __len__(self) -> int:
        """Return the total number of indexed service providers."""
        return sum(len(matches) for matches in self._type_providers.values())


def _provider_label(provider: _Provider) -> str:
    provides = getattr(provider, "provides", None)
    name = getattr(provides, "__name__", None)
    if isinstance(name, str):
        return name
    return type(provider).__name__


def _callable_return_type(provided: Callable[..., Any] | None) -> type[Any] | None:
    if isinstance(provided, type):
        return provided
    if provided is None:
        return None

    annotation: Any
    try:
        annotation = get_type_hints(provided).get("return", Signature.empty)
    except (AttributeError, NameError, TypeError, ValueError):
        try:
            annotation = signature(provided).return_annotation
        except (TypeError, ValueError):
            return None

    if annotation in (Signature.empty, Any, None, NoneType) or isinstance(annotation, str):
        return None

    origin = get_origin(annotation)
    if origin is Annotated:
        annotation = get_args(annotation)[0]
        origin = get_origin(annotation)
    if origin is UnionType:
        return None
    if origin is not None:
        annotation = origin

    return annotation if isinstance(annotation, type) else None
