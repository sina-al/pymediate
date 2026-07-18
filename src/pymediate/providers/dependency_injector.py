"""Dependency Injector integration for PyMediate service resolution."""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from inspect import Signature, isawaitable, iscoroutine, signature
from types import NoneType, UnionType
from typing import Annotated, Any, cast, get_args, get_origin, get_type_hints

from dependency_injector import containers, providers

from ..service import ServiceNotFoundError

type _Provider = providers.Provider[Any]


@dataclass(frozen=True, slots=True)
class _Registration:
    service_type: type[Any]
    provider: _Provider
    path: str


class DependencyInjectorServiceProvider:
    """ServiceProvider backed by a Dependency Injector container.

    Indexes services from the container without resolving them, then delegates each
    service resolution to its original Dependency Injector provider. Class-backed
    factories and singletons, object providers, and factories with concrete return
    annotations are discovered automatically.

    Child ``providers.Container`` providers are indexed recursively in declaration
    order. Other provider dependencies are not traversed, so providers reachable only
    through injection are not accidentally exposed as PyMediate services.

    Examples:
        ```python
        from dependency_injector import containers, providers
        from pymediate import Mediator
        from pymediate.providers import DependencyInjectorServiceProvider

        class AppContainer(containers.DeclarativeContainer):
            database = providers.Singleton(Database)
            create_user = providers.Factory(CreateUserHandler, database=database)

        container = AppContainer()
        services = DependencyInjectorServiceProvider(container)
        mediator = Mediator(services)
        ```

    Note:
        The provider graph and inferred types are a construction-time snapshot.
        Rebuild this service provider after adding providers or applying an override
        that changes a provider's output type. Overrides that preserve the output type
        continue to work because service resolution remains delegated to the original
        Dependency Injector provider.

    See Also:
        - ServiceProvider: The protocol this class implements.
        - Services: A DI-container-free alternative for manual service registration.
    """

    def __init__(self, container: containers.Container) -> None:
        """Index services declared by a Dependency Injector container.

        Args:
            container: A ``DeclarativeContainer`` or ``DynamicContainer`` instance.

        Raises:
            TypeError: If ``container`` is not a Dependency Injector container, or a
                service provider's output type cannot be determined without
                resolving it.
            ValueError: If nested containers form a cycle.
        """
        if not isinstance(container, containers.Container):
            raise TypeError("container must be a dependency_injector.containers.Container")

        self._container = container
        self._type_providers: dict[type[Any], list[_Registration]] = {}
        self._registration_order: list[_Registration] = []

        self._scan_container(container, path="", active_containers=set())

    def _scan_container(
        self,
        container: containers.Container,
        *,
        path: str,
        active_containers: set[int],
    ) -> None:
        container_id = id(container)
        if container_id in active_containers:
            location = path.removesuffix(".") or "<root>"
            raise ValueError(f"nested Dependency Injector container cycle at '{location}'")

        active_containers.add(container_id)
        declared = cast(Mapping[str, _Provider], container.providers)

        try:
            for name, provider in declared.items():
                provider_path = f"{path}{name}"
                effective = provider.last_overriding or provider

                if isinstance(effective, providers.Container):
                    child = cast(containers.Container, effective.container)
                    self._scan_container(
                        child,
                        path=f"{provider_path}.",
                        active_containers=active_containers,
                    )
                    continue

                service_type = self._service_type(provider, effective, provider_path)
                if service_type is not None:
                    self._register(service_type, provider, provider_path)
        finally:
            active_containers.remove(container_id)

    def _service_type(
        self,
        provider: _Provider,
        effective: _Provider,
        path: str,
    ) -> type[Any] | None:
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

        if isinstance(effective, providers.Coroutine):
            raise TypeError(
                f"provider '{path}' is asynchronous; PyMediate service resolution is "
                "synchronous even when handlers are asynchronous"
            )

        if isinstance(
            effective,
            (providers.Factory, providers.BaseSingleton, providers.Callable),
        ):
            service_type = _callable_return_type(effective.provides)
            if service_type is not None:
                return service_type
            raise TypeError(_opaque_provider_message(path))

        if isinstance(effective, providers.BaseResource):
            raise TypeError(_opaque_provider_message(path))

        raise TypeError(_opaque_provider_message(path))

    def _register(self, service_type: type[Any], provider: _Provider, path: str) -> None:
        registration = _Registration(service_type, provider, path)
        self._type_providers.setdefault(service_type, []).append(registration)
        self._registration_order.append(registration)

    def _resolve(self, registration: _Registration) -> Any:
        instance = registration.provider()
        if isawaitable(instance):
            if iscoroutine(instance):
                instance.close()
            cancel = getattr(instance, "cancel", None)
            if callable(cancel):
                cancel()
            raise TypeError(
                f"provider '{registration.path}' resolved asynchronously; PyMediate "
                "service providers must construct services synchronously"
            )
        if not isinstance(instance, registration.service_type):
            raise TypeError(
                f"provider '{registration.path}' produced {type(instance).__name__}, not its "
                f"indexed service type {registration.service_type.__name__}; rebuild the "
                "DependencyInjectorServiceProvider after a type-changing override"
            )
        return instance

    def get[ServiceT](self, service_type: type[ServiceT]) -> ServiceT:
        """Get the first registered instance of the exact type.

        Args:
            service_type: The exact type of service to get.

        Returns:
            The first registered instance of the exact type.

        Raises:
            ServiceNotFoundError: If no instance of the exact type is registered.
            TypeError: If the matching Dependency Injector provider resolves
                asynchronously.
        """
        registrations = self._type_providers.get(service_type)
        if registrations is None:
            raise ServiceNotFoundError(service_type, list(self._type_providers))
        return cast(ServiceT, self._resolve(registrations[0]))

    def get_all(self, service_type: type[Any]) -> Sequence[Any]:
        """Get all instances of the type, including subclasses, in declaration order.

        Args:
            service_type: The type, abstract base, or runtime-checkable protocol to
                resolve.

        Returns:
            All matching instances in declaration order, or an empty sequence.

        Raises:
            TypeError: If a matching Dependency Injector provider resolves
                asynchronously.
        """
        result: list[Any] = []
        for registration in self._registration_order:
            try:
                matches = issubclass(registration.service_type, service_type)
            except TypeError:
                instance = self._resolve(registration)
                if isinstance(instance, service_type):
                    result.append(instance)
            else:
                if matches:
                    result.append(self._resolve(registration))
        return result

    def has(self, service_type: type[Any]) -> bool:
        """Check whether any instance of the exact type is registered.

        Args:
            service_type: The type to check for.

        Returns:
            True if at least one instance of the exact type is registered.
        """
        return service_type in self._type_providers

    def get_all_types(self) -> tuple[type[Any], ...]:
        """Get every exact type that has at least one registered instance.

        Returns:
            All registered service types in first-declaration order.
        """
        return tuple(self._type_providers)

    def __len__(self) -> int:
        """Return the total number of indexed service providers."""
        return len(self._registration_order)


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


def _opaque_provider_message(path: str) -> str:
    return (
        f"cannot determine the service type for provider '{path}' without resolving it; "
        "use a class-backed provider or add a concrete return annotation"
    )
