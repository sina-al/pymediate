"""A bookmark service wired to a Dishka container through a hand-written ServiceProvider.

``ServiceProvider`` is a ``Protocol``, not a base class you must inherit from a fixed
implementation. Any object that answers two questions - "is this type registered?" and
"give me the instance for this type" - can drive a ``Mediator``. This example implements
those two methods over `Dishka <https://github.com/reagento/dishka>`_, a container
PyMediate has no built-in integration with, and hands the result to ``Mediator``
unchanged.

The handlers, the behavior, and the mediator wiring below are the same code they would be
under ``Services`` or the ``dependency-injector`` integration from
`examples/100-dependency-injection/`. Only the provider changed.
"""

import asyncio
from dataclasses import dataclass
from typing import Any

from dishka import DEFAULT_COMPONENT, Container, DependencyKey, Provider, Scope, make_container
from pymediate import (
    Mediator,
    Next,
    PipelineBehavior,
    Request,
    RequestHandler,
    ServiceNotFoundError,
    ServiceProvider,
)

# ---- The provider: two methods over someone else's container ----


class DishkaServiceProvider(ServiceProvider):
    """Resolves PyMediate services from a Dishka container.

    Inheriting from ``ServiceProvider`` is optional - the protocol matches structurally -
    but it makes the intent explicit and lets a type checker confirm both methods are
    present and correctly typed.
    """

    def __init__(self, container: Container) -> None:
        self._container = container

    def __getitem__[ServiceT](self, service_type: type[ServiceT]) -> ServiceT:
        # Check first, then resolve. Dishka raises its own NoFactoryError on a miss;
        # translating it here keeps callers on PyMediate's documented exception.
        if service_type not in self:
            raise ServiceNotFoundError(service_type, self._registered_types())

        return self._container.get(service_type)

    def __contains__(self, service_type: type) -> bool:
        # Ask the registry, not the container: looking up a factory answers whether the
        # type is registered without building the instance. `container.get()` would
        # construct it as a side effect of the question.
        key = DependencyKey(service_type, DEFAULT_COMPONENT)
        return self._container.registry.get_factory(key) is not None

    def _registered_types(self) -> list[type]:
        """Collect registered types so a failed lookup can list what is available."""
        return [key.type_hint for key in self._container.registry.factories]


# ---- Domain ----


@dataclass
class Bookmark:
    """A saved link."""

    url: str
    title: str


class BookmarkStore:
    """In-memory storage, shared by both handlers through the container."""

    def __init__(self) -> None:
        self.saved: dict[str, Bookmark] = {}


class AuditLog:
    """A record of dispatched requests, written by the pipeline behavior."""

    def __init__(self) -> None:
        self.entries: list[str] = []


# ---- Requests and handlers ----


@dataclass
class SaveBookmark(Request[Bookmark]):
    """Save a link; responds with the stored Bookmark."""

    url: str
    title: str


@dataclass
class ListBookmarks(Request[list[Bookmark]]):
    """List every saved bookmark, most recently saved last."""


class SaveBookmarkHandler(RequestHandler[SaveBookmark]):
    """Writes to the store. Dishka injects the store by its constructor annotation."""

    def __init__(self, store: BookmarkStore) -> None:
        self._store = store

    async def __call__(self, request: SaveBookmark) -> Bookmark:
        bookmark = Bookmark(url=request.url, title=request.title)
        self._store.saved[request.url] = bookmark
        return bookmark


class ListBookmarksHandler(RequestHandler[ListBookmarks]):
    """Reads the same store instance the save handler writes to."""

    def __init__(self, store: BookmarkStore) -> None:
        self._store = store

    async def __call__(self, request: ListBookmarks) -> list[Bookmark]:
        return list(self._store.saved.values())


class AuditBehavior(PipelineBehavior[Request[Any]]):
    """Records each dispatched request type.

    The mediator resolves this class through the same provider as the handlers, which is
    what makes ``__contains__`` load-bearing: a behavior listed in ``behaviors=`` that the
    container does not provide is rejected when the ``Mediator`` is constructed.
    """

    def __init__(self, audit: AuditLog) -> None:
        self._audit = audit

    async def __call__(self, request: Request[Any], next: Next[Any]) -> Any:
        self._audit.entries.append(type(request).__name__)
        return await next()


# ---- Composition root ----


def build_services() -> DishkaServiceProvider:
    """Declare every service in a Dishka container and wrap it in the custom provider.

    Dishka resolves constructor dependencies from type annotations, so registering a
    class is enough for it to supply that class's own dependencies.
    """
    provider = Provider(scope=Scope.APP)
    provider.provide(BookmarkStore)
    provider.provide(AuditLog)
    provider.provide(SaveBookmarkHandler)
    provider.provide(ListBookmarksHandler)
    provider.provide(AuditBehavior)

    return DishkaServiceProvider(make_container(provider))


def build_mediator(services: DishkaServiceProvider | None = None) -> Mediator:
    """Build a mediator over the Dishka-backed provider.

    This call is identical to the one in every other example. The mediator has no
    knowledge of which container is underneath.
    """
    services = services if services is not None else build_services()
    return Mediator(services, behaviors=[AuditBehavior])


async def main() -> None:
    """Dispatch two requests through the custom provider and show the audit log."""
    services = build_services()
    mediator = build_mediator(services)

    await mediator.send(SaveBookmark(url="https://python.org", title="Python"))
    await mediator.send(SaveBookmark(url="https://pymediate.sina-al.uk", title="PyMediate"))

    for bookmark in await mediator.send(ListBookmarks()):
        print(f"{bookmark.title}: {bookmark.url}")

    print(f"Audited: {services[AuditLog].entries}")


if __name__ == "__main__":
    asyncio.run(main())
