"""Service collection and provider for dependency injection.

Construct ``Services`` with the instances to register, then resolve them by their
exact type. ``Services`` is itself a ``ServiceProvider``, so it can be passed
straight to a ``Mediator``.

Examples:
    ```python
    from pymediate import Services

    class Cache:
        pass

    cache = Cache()
    services = Services(cache)

    assert services[Cache] is cache
    ```
"""

from typing import Any, Protocol, cast

from .errors import ServiceAlreadyRegisteredError


class ServiceNotFoundError(KeyError):
    """Raised when a requested service type is not registered.

    Subclasses ``KeyError`` because a provider is a read-only mapping of type to
    instance, and ``provider[service_type]`` is its subscript: a missing type is a
    missing key. ``except KeyError`` therefore catches a failed lookup, while
    ``str(error)`` still renders the full multi-line message (``KeyError``'s own
    ``__str__`` would ``repr()`` it instead).

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

        self._message = (
            f"No service of type '{service_type.__name__}' is registered.\n"
            f"Available service types: {available_str}"
        )
        super().__init__(self._message)

    def __str__(self) -> str:
        """Return the full message, bypassing ``KeyError``'s ``repr``-wrapping ``__str__``."""
        return self._message


class ServiceProvider(Protocol):
    """Protocol for resolving registered service instances.

    ``provider[Type]`` matches an exact registered type.

    ``Services`` is the built-in implementation.
    ``DependencyInjectorServiceProvider`` adapts a Dependency Injector container.
    A custom provider can use another resolution and lifetime policy while
    implementing the same two operations.

    Note:
        The protocol is read-only. Thread-safety and mutation behavior depend on
        the implementation.
    """

    def __getitem__[ServiceT](self, service_type: type[ServiceT]) -> ServiceT:
        """Get the registered instance of the exact type.

        Uses exact type matching only - a request for a base class doesn't match a
        registered subclass.

        Args:
            service_type: The exact type of service to get.

        Returns:
            The registered instance of the exact type.

        Raises:
            ServiceNotFoundError: If no instance of the exact type is registered.
        """
        ...

    def __contains__(self, service_type: type) -> bool:
        """Check whether an instance of the exact type is registered.

        Like `__getitem__`, this uses exact type matching only.

        Args:
            service_type: The exact type to check for.

        Returns:
            True if an instance of the exact type is registered.
        """
        ...


class Services(ServiceProvider):
    """Immutable collection of service instances, keyed by their exact type.

    Pass every instance to the constructor; the collection holds one instance per
    concrete type (`type(instance)`) and resolves it by that exact type. There is
    no separate build step - a `Services` is already a `ServiceProvider`, so it can
    be handed directly to a `Mediator`.

    Combine two collections with `|` to replace services deliberately - the right
    operand wins, and both operands are left unchanged.

    Examples:
        ```python
        from pymediate import Services

        class Store:
            pass

        class Cache:
            pass

        store = Store()
        services = Services(store, Cache())

        assert services[Store] is store
        assert Cache in services
        assert len(services) == 2

        replacement = Store()
        overridden = services | Services(replacement)

        assert overridden[Store] is replacement
        assert services[Store] is store  # the original is unchanged
        ```

    """

    def __init__(self, *instances: object) -> None:
        """Create a collection holding the given service instances.

        Args:
            *instances: The service instances to register, each keyed by its
                concrete type. No two may share a type.

        Raises:
            ValueError: If any instance is None.
            ServiceAlreadyRegisteredError: If two instances share a concrete type.
        """
        self._services: dict[type, Any] = {}

        for instance in instances:
            if instance is None:
                raise ValueError("Cannot register None as a service instance")

            service_type = type(instance)
            if service_type in self._services:
                raise ServiceAlreadyRegisteredError(service_type)

            self._services[service_type] = instance

    @classmethod
    def _of(cls, services: dict[type, Any]) -> "Services":
        """Build a collection from an already-validated type-to-instance mapping."""
        combined = cls()
        combined._services = services
        return combined

    def __getitem__[ServiceT](self, service_type: type[ServiceT]) -> ServiceT:
        """Get the registered instance of the exact type.

        Args:
            service_type: The type of service to get.

        Returns:
            The registered instance of the requested type.

        Raises:
            ServiceNotFoundError: If no instance of the requested type is registered.
        """
        if service_type not in self._services:
            raise ServiceNotFoundError(service_type, list(self._services))

        return cast(ServiceT, self._services[service_type])

    def __contains__(self, service_type: type) -> bool:
        """Check whether an instance of the exact type is registered.

        Args:
            service_type: The type to check for.

        Returns:
            True if an instance of the exact type is registered.
        """
        return service_type in self._services

    def __or__(self, other: "Services") -> "Services":
        """Combine two collections, letting the right operand win on shared types.

        Both operands are left unchanged. Unlike the constructor, a type present in
        both collections is not an error - overriding is this operator's purpose,
        which is what makes swapping a fake into an existing wiring explicit.

        Args:
            other: The collection whose services take precedence.

        Returns:
            A new collection holding both operands' services.
        """
        if not isinstance(other, Services):
            return NotImplemented

        return Services._of({**self._services, **other._services})

    def __len__(self) -> int:
        """Return the number of registered service instances."""
        return len(self._services)

    def __repr__(self) -> str:
        """Return the constructor call that would rebuild this collection."""
        type_names = ", ".join(t.__name__ for t in self._services)
        return f"Services({type_names})"
