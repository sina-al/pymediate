"""A user directory wired with a dependency-injector container — PyMediate's `di` extra.

Demonstrates the optional integration in ``pymediate.providers``: declare handlers and
their dependencies in a ``DeclarativeContainer``, wrap the container in
``DependencyInjectorServiceProvider``, and hand that to ``Mediator`` — the container
takes over the wiring that ``Services`` does by hand in the basic examples. Requires the
``di`` extra: ``pip install pymediate[di]``.
"""

from dataclasses import dataclass, field

from dependency_injector import containers, providers
from pymediate import RequestHandler, Mediator, Request
from pymediate.providers import DependencyInjectorServiceProvider


@dataclass
class User:
    """A directory entry."""

    user_id: int
    username: str


@dataclass
class UserRepository:
    """In-memory storage (a stand-in for a real database)."""

    users: dict[int, User] = field(default_factory=dict)
    next_id: int = 1


class UserNotFoundError(Exception):
    """Raised when a request references a user id that doesn't exist."""


# ---- Requests: each declares the response type it resolves to ----


@dataclass
class RegisterUser(Request[User]):
    """Register a user by name; responds with the created User."""

    username: str


@dataclass
class GetUser(Request[User]):
    """Look up a user by id; responds with the stored User."""

    user_id: int


# ---- Handlers: dependencies arrive through constructors, injected by the container ----


class RegisterUserHandler(RequestHandler[RegisterUser]):
    """Creates users in the repository."""

    def __init__(self, repository: UserRepository) -> None:
        self._repository = repository

    def __call__(self, request: RegisterUser) -> User:
        user = User(user_id=self._repository.next_id, username=request.username)
        self._repository.users[user.user_id] = user
        self._repository.next_id += 1
        return user


class GetUserHandler(RequestHandler[GetUser]):
    """Looks up existing users."""

    def __init__(self, repository: UserRepository) -> None:
        self._repository = repository

    def __call__(self, request: GetUser) -> User:
        user = self._repository.users.get(request.user_id)
        if user is None:
            raise UserNotFoundError(f"No user with id {request.user_id}")
        return user


class AppContainer(containers.DeclarativeContainer):
    """The composition root: one Singleton repository shared by Factory-built handlers."""

    repository = providers.Singleton(UserRepository)
    register_user_handler = providers.Factory(RegisterUserHandler, repository=repository)
    get_user_handler = providers.Factory(GetUserHandler, repository=repository)


def build_mediator(container: AppContainer | None = None) -> Mediator:
    """Wrap a container in a ServiceProvider and hand it to the mediator."""
    container = container if container is not None else AppContainer()
    return Mediator(DependencyInjectorServiceProvider(container))


def main() -> None:
    """Run a short demo of the user directory."""
    mediator = build_mediator()

    alice = mediator.send(RegisterUser(username="alice"))
    print(f"Registered: {alice}")

    found = mediator.send(GetUser(user_id=alice.user_id))
    print(f"Found: {found.username}")


if __name__ == "__main__":
    main()
