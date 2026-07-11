"""Tests for the with-dependency-injector example — the `uv run pytest` entrypoint."""

import pytest
from pymediate.providers import DependencyInjectorServiceProvider
from pymediate.sync import Mediator

from app import (
    AppContainer,
    GetUser,
    RegisterUser,
    RegisterUserHandler,
    User,
    UserNotFoundError,
    UserRepository,
    build_mediator,
)


@pytest.fixture
def container() -> AppContainer:
    return AppContainer()


@pytest.fixture
def mediator(container: AppContainer) -> Mediator:
    return build_mediator(container)


def test_register_user_returns_created_user(mediator: Mediator) -> None:
    user = mediator.send(RegisterUser(username="alice"))

    assert isinstance(user, User)
    assert user.user_id == 1
    assert user.username == "alice"


def test_get_user_finds_registered_user(mediator: Mediator) -> None:
    registered = mediator.send(RegisterUser(username="bob"))

    found = mediator.send(GetUser(user_id=registered.user_id))

    assert found == registered


def test_get_unknown_user_raises(mediator: Mediator) -> None:
    with pytest.raises(UserNotFoundError):
        mediator.send(GetUser(user_id=999))


def test_singleton_repository_is_shared(container: AppContainer, mediator: Mediator) -> None:
    # The Singleton provider hands the same repository to every handler the container
    # builds, so state written through the mediator is visible on the container's instance.
    mediator.send(RegisterUser(username="carol"))

    assert container.repository().users[1].username == "carol"


def test_factory_handlers_share_the_singleton(container: AppContainer) -> None:
    provider = DependencyInjectorServiceProvider(container)

    first = provider.get(RegisterUserHandler)
    second = provider.get(RegisterUserHandler)

    # Factory providers build a fresh handler per resolution...
    assert first is not second
    # ...but each one wraps the same Singleton repository.
    assert first._repository is second._repository
    assert isinstance(first._repository, UserRepository)
