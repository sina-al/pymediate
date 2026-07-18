"""A user directory wired with PyMediate's ``dependency-injector`` integration.

Demonstrates the optional integration in ``pymediate.providers`` (shown here on the
sync API; the provider is loop-agnostic and works identically with async handlers and
the top-level ``pymediate`` mediator): declare handlers and their dependencies in a
``DeclarativeContainer``, wrap the container in ``DependencyInjectorServiceProvider``,
and hand that to ``Mediator``. The ``pymediate[di]`` dependency declared by this example
installs the optional integration.

Three provider lifetimes appear, each resolved by type rather than by name:

- **Factory** (``register_user_handler``, ``get_user_handler``, ``transaction_behavior``)
  — a fresh instance every time the container is asked, so each dispatch gets its own
  handler object.
- **Singleton** (``repository``) — one instance for the life of the container, shared by
  every handler that's built afterward.
- **``ContextLocalSingleton``** (``unit_of_work``) — one instance in the current
  ``contextvars`` context until the provider is reset. Both the handler and behavior resolve
  the same ``UnitOfWork`` before that reset.
"""

from dataclasses import dataclass, field

from dependency_injector import containers, providers
from pymediate.providers import DependencyInjectorServiceProvider
from pymediate.sync import Mediator, Next, PipelineBehavior, Request, RequestHandler


@dataclass
class User:
    """A directory entry."""

    user_id: int
    username: str


@dataclass
class UserRepository:
    """In-memory storage. A Singleton provides one repository for the application."""

    users: dict[int, User] = field(default_factory=dict)
    next_id: int = 1


@dataclass
class UnitOfWork:
    """A per-request transaction log. A ``ContextLocalSingleton``: one per logical scope.

    A database-backed unit of work would open a transaction and commit or roll it back at the
    request boundary. This implementation records operations so tests can observe which
    components shared a scope.
    """

    entries: list[str] = field(default_factory=list)

    def record(self, entry: str) -> None:
        """Append an entry to this scope's log."""
        self.entries.append(entry)


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
    """Creates users in the repository and records the write in the unit of work."""

    def __init__(self, repository: UserRepository, unit_of_work: UnitOfWork) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    def __call__(self, request: RegisterUser) -> User:
        user = User(user_id=self._repository.next_id, username=request.username)
        self._repository.users[user.user_id] = user
        self._repository.next_id += 1
        self._unit_of_work.record(f"registered {user.username!r}")
        return user


class GetUserHandler(RequestHandler[GetUser]):
    """Looks up existing users. Read-only, so it has no need for the unit of work."""

    def __init__(self, repository: UserRepository) -> None:
        self._repository = repository

    def __call__(self, request: GetUser) -> User:
        user = self._repository.users.get(request.user_id)
        if user is None:
            raise UserNotFoundError(f"No user with id {request.user_id}")
        return user


class TransactionLoggingBehavior(PipelineBehavior[Request]):
    """Brackets every dispatch with begin/commit markers in that scope's unit of work.

    The behavior and ``RegisterUserHandler`` both resolve ``unit_of_work`` from the
    container. Within one dispatch that's the same ``ContextLocalSingleton`` instance,
    so ``entries`` ends up interleaved: ``["begin", "registered 'alice'", "commit"]``.
    """

    def __init__(self, unit_of_work: UnitOfWork) -> None:
        self._unit_of_work = unit_of_work

    def __call__(self, request: Request[object], next: Next[object]) -> object:
        self._unit_of_work.record("begin")
        response = next()
        self._unit_of_work.record("commit")
        return response


class AppContainer(containers.DeclarativeContainer):
    """The composition root: Factory, Singleton, and ContextLocalSingleton, side by side."""

    repository = providers.Singleton(UserRepository)
    unit_of_work = providers.ContextLocalSingleton(UnitOfWork)

    transaction_behavior = providers.Factory(TransactionLoggingBehavior, unit_of_work=unit_of_work)
    register_user_handler = providers.Factory(
        RegisterUserHandler, repository=repository, unit_of_work=unit_of_work
    )
    get_user_handler = providers.Factory(GetUserHandler, repository=repository)


def build_mediator(container: AppContainer | None = None) -> Mediator:
    """Wrap a container in a ServiceProvider and hand it to the mediator."""
    container = container if container is not None else AppContainer()
    return Mediator(DependencyInjectorServiceProvider(container))


def main() -> None:
    """Register two users as two separate request scopes, each with its own unit of work."""
    container = AppContainer()
    mediator = build_mediator(container)

    alice = mediator.send(RegisterUser(username="alice"))
    print(f"Registered: {alice}")
    print(f"Unit of work: {container.unit_of_work().entries}")

    # Request middleware must reset this provider in a finally block at each scope boundary.
    container.unit_of_work.reset()

    bob = mediator.send(RegisterUser(username="bob"))
    print(f"Registered: {bob}")
    print(f"Unit of work: {container.unit_of_work().entries}")  # bob's scope, not alice's


if __name__ == "__main__":
    main()
