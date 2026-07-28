"""Tests for the 120-custom-provider example - the `uv run pytest` entrypoint."""

import pytest
from dishka import Provider, Scope, make_container
from pymediate import Mediator, ServiceNotFoundError

from app import (
    AuditBehavior,
    AuditLog,
    Bookmark,
    BookmarkStore,
    DishkaServiceProvider,
    ListBookmarks,
    ListBookmarksHandler,
    SaveBookmark,
    SaveBookmarkHandler,
    build_mediator,
    build_services,
)


@pytest.fixture
def services() -> DishkaServiceProvider:
    return build_services()


@pytest.fixture
def mediator(services: DishkaServiceProvider) -> Mediator:
    return build_mediator(services)


# ---- The mediator drives the custom provider like any other ----


async def test_request_resolves_through_the_custom_provider(mediator: Mediator) -> None:
    saved = await mediator.send(SaveBookmark(url="https://python.org", title="Python"))

    assert saved == Bookmark(url="https://python.org", title="Python")


async def test_handlers_share_the_container_managed_store(mediator: Mediator) -> None:
    # Both handlers declare BookmarkStore in their constructor; an APP-scoped Dishka
    # provider hands both the same instance, so a write is visible to the reader.
    await mediator.send(SaveBookmark(url="https://python.org", title="Python"))

    listed = await mediator.send(ListBookmarks())

    assert listed == [Bookmark(url="https://python.org", title="Python")]


async def test_behavior_resolves_through_the_provider_too(
    services: DishkaServiceProvider, mediator: Mediator
) -> None:
    await mediator.send(SaveBookmark(url="https://python.org", title="Python"))
    await mediator.send(ListBookmarks())

    assert services[AuditLog].entries == ["SaveBookmark", "ListBookmarks"]


# ---- The two protocol methods ----


def test_getitem_returns_the_registered_instance(services: DishkaServiceProvider) -> None:
    handler = services[SaveBookmarkHandler]

    assert isinstance(handler, SaveBookmarkHandler)


def test_getitem_raises_service_not_found_for_an_unregistered_type(
    services: DishkaServiceProvider,
) -> None:
    class Unregistered:
        pass

    with pytest.raises(ServiceNotFoundError) as caught:
        services[Unregistered]

    # PyMediate's error, not Dishka's NoFactoryError, and a KeyError like any failed
    # subscript lookup.
    assert caught.value.service_type is Unregistered
    assert isinstance(caught.value, KeyError)


def test_contains_reports_registration(services: DishkaServiceProvider) -> None:
    class Unregistered:
        pass

    assert SaveBookmarkHandler in services
    assert ListBookmarksHandler in services
    assert Unregistered not in services


def test_contains_matches_the_exact_type_only() -> None:
    # PyMediate resolves by exact type: a registered subclass must not satisfy a request
    # for its base class.
    class Base:
        pass

    class Derived(Base):
        pass

    provider = Provider(scope=Scope.APP)
    provider.provide(Derived)
    services = DishkaServiceProvider(make_container(provider))

    assert Derived in services
    assert Base not in services


def test_contains_does_not_construct_the_service() -> None:
    # The reason __contains__ consults the registry instead of calling container.get():
    # asking whether a type is registered must not build it.
    constructed: list[str] = []

    class Tracked:
        def __init__(self) -> None:
            constructed.append("built")

    provider = Provider(scope=Scope.APP)
    provider.provide(Tracked)
    services = DishkaServiceProvider(make_container(provider))

    assert Tracked in services
    assert Tracked in services
    assert constructed == []

    services[Tracked]

    assert constructed == ["built"]


def test_mediator_rejects_a_behavior_the_container_does_not_provide() -> None:
    # The mediator checks `behavior_class in provider` when it is constructed. This is
    # the only place PyMediate itself calls __contains__.
    provider = Provider(scope=Scope.APP)
    provider.provide(BookmarkStore)
    provider.provide(SaveBookmarkHandler)
    services = DishkaServiceProvider(make_container(provider))

    with pytest.raises(Exception, match="not registered with the service provider"):
        Mediator(services, behaviors=[AuditBehavior])
