"""``ServiceProvider`` is a Protocol: satisfy it with anything, and the mediator never knows.

``Services.provider()`` and ``DependencyInjectorServiceProvider`` are the two providers
the other examples use, but neither is special — both just implement PyMediate's
``ServiceProvider`` Protocol (``get``, ``get_all``, ``has``, ``get_all_types``,
``__len__``). This example implements a third one from scratch, over
``TypeRegistry`` — a hand-rolled,
name-based registry that has nothing to do with PyMediate and wasn't built with it in
mind, the kind of container many existing apps already have lying around. Wiring it in
touches nothing but construction: every ``mediator.send()`` call site is unchanged.
"""

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from pymediate import Mediator, Request, RequestHandler, ServiceNotFoundError

# ---- An existing app container, unrelated to PyMediate ----


class TypeRegistry:
    """A hand-rolled service registry — the kind many apps already have.

    Instances are registered under whatever name the caller likes and resolved by that
    same name. This container doesn't know PyMediate exists; adapting it to PyMediate's
    type-based resolution is the whole job of ``TypeRegistryServiceProvider`` below.
    """

    def __init__(self) -> None:
        self._by_name: dict[str, object] = {}

    def register(self, name: str, instance: object) -> None:
        """Register an instance under a name."""
        self._by_name[name] = instance

    def resolve(self, name: str) -> object:
        """Look up an instance by the name it was registered under."""
        return self._by_name[name]

    def all(self) -> list[object]:
        """Every registered instance, in registration order."""
        return list(self._by_name.values())


# ---- The adapter: implements ServiceProvider over TypeRegistry ----


class TypeRegistryServiceProvider:
    """Implements PyMediate's ``ServiceProvider`` Protocol over a ``TypeRegistry``.

    PyMediate resolves by concrete type; ``TypeRegistry`` resolves by name. This
    adapter bridges that gap once, at construction, by indexing every registered
    instance by its type — the same scan-once-and-cache approach
    ``DependencyInjectorServiceProvider`` uses for a real DI container.
    """

    def __init__(self, registry: TypeRegistry) -> None:
        self._by_type: dict[type, list[Any]] = {}
        self._order: list[Any] = []
        for instance in registry.all():
            self._by_type.setdefault(type(instance), []).append(instance)
            self._order.append(instance)

    def get(self, service_type: type[Any]) -> Any:
        """Get the first registered instance of the exact type."""
        instances = self._by_type.get(service_type)
        if not instances:
            raise ServiceNotFoundError(service_type, list(self._by_type.keys()))
        return instances[0]

    def get_all(self, service_type: type[Any]) -> Sequence[Any]:
        """Get all instances of the type, including subclasses, in registration order."""
        return [instance for instance in self._order if isinstance(instance, service_type)]

    def has(self, service_type: type) -> bool:
        """Check whether any instance of the exact type is registered."""
        return service_type in self._by_type

    def get_all_types(self) -> tuple[type, ...]:
        """Get every exact type that has at least one registered instance."""
        return tuple(self._by_type.keys())

    def __len__(self) -> int:
        """Return how many service instances are registered in total."""
        return len(self._order)


# ---- A tiny application: two handlers, one shared collaborator ----


class Logger:
    """A shared collaborator, to show the adapter resolving the same instance twice."""

    def __init__(self) -> None:
        self.lines: list[str] = []

    def log(self, line: str) -> None:
        """Record a line."""
        self.lines.append(line)


@dataclass
class Add(Request[int]):
    """Add two numbers."""

    a: int
    b: int


class AddHandler(RequestHandler[Add]):
    """Adds, and logs the result."""

    def __init__(self, logger: Logger) -> None:
        self._logger = logger

    async def __call__(self, request: Add) -> int:
        result = request.a + request.b
        self._logger.log(f"{request.a} + {request.b} = {result}")
        return result


@dataclass
class Multiply(Request[int]):
    """Multiply two numbers."""

    a: int
    b: int


class MultiplyHandler(RequestHandler[Multiply]):
    """Multiplies, and logs the result."""

    def __init__(self, logger: Logger) -> None:
        self._logger = logger

    async def __call__(self, request: Multiply) -> int:
        result = request.a * request.b
        self._logger.log(f"{request.a} * {request.b} = {result}")
        return result


def build_registry(logger: Logger | None = None) -> TypeRegistry:
    """Populate a TypeRegistry the way an existing app already would — by name."""
    logger = logger if logger is not None else Logger()
    registry = TypeRegistry()
    registry.register("logger", logger)
    registry.register("add_handler", AddHandler(logger))
    registry.register("multiply_handler", MultiplyHandler(logger))
    return registry


def build_mediator(logger: Logger | None = None) -> Mediator:
    """Wire a mediator from the custom provider — the only line that mentions it."""
    return Mediator(TypeRegistryServiceProvider(build_registry(logger)))


async def main() -> None:
    """Send two requests through a mediator built from the from-scratch provider."""
    logger = Logger()
    mediator = build_mediator(logger)

    total = await mediator.send(Add(a=2, b=3))
    print(f"2 + 3 = {total}")

    product = await mediator.send(Multiply(a=4, b=5))
    print(f"4 * 5 = {product}")

    print("Logger saw:", logger.lines)


if __name__ == "__main__":
    asyncio.run(main())
