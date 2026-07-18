"""Tests for the 100-dependency-injection-sync example — the `uv run pytest` entrypoint."""

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


def test_context_local_singleton_is_shared_within_one_dispatch(
    container: AppContainer, mediator: Mediator
) -> None:
    # TransactionLoggingBehavior and RegisterUserHandler each resolve `unit_of_work`
    # separately, but within one dispatch (no scope boundary crossed) the
    # ContextLocalSingleton hands both the same instance, so their writes interleave.
    mediator.send(RegisterUser(username="dave"))

    assert container.unit_of_work().entries == ["begin", "registered 'dave'", "commit"]


def test_context_local_singleton_is_not_shared_across_scopes(
    container: AppContainer, mediator: Mediator
) -> None:
    mediator.send(RegisterUser(username="erin"))
    first_scope = container.unit_of_work()

    container.unit_of_work.reset()  # simulate moving to the next request

    mediator.send(RegisterUser(username="frank"))
    second_scope = container.unit_of_work()

    assert first_scope is not second_scope
    assert "registered 'erin'" in first_scope.entries
    assert "registered 'erin'" not in second_scope.entries
    assert "registered 'frank'" in second_scope.entries
