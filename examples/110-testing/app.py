"""The application under test: deliberately small, since the tests are the point.

A tiny user directory: ``GetUserHandler`` is a leaf (no dependencies that dispatch
anything), ``RegisterUserHandler`` composes — it creates a user, then dispatches a
``SendWelcomeEmail`` request through an injected sender — and ``GreetHandler`` exists
only to carry a constructor argument for the registry-gotcha tests.

Nothing here imports pytest, a mediator fake, or a web framework. That's what the four
test files next to this one are demonstrating: a handler is a plain callable with
injected dependencies, so testing it is testing any other Python object.
"""

import sys
from dataclasses import dataclass
from typing import Protocol, TypeVar

from pymediate import Mediator, Request, RequestHandler, Services

ResponseT = TypeVar("ResponseT")


@dataclass
class User:
    """A directory entry."""

    user_id: int
    username: str
    email: str


class UserRepository:
    """In-memory storage (a stand-in for a real database)."""

    def __init__(self) -> None:
        self._users: dict[int, User] = {}
        self._next_id = 1

    def create(self, username: str, email: str) -> User:
        """Insert a new user and return it."""
        user = User(user_id=self._next_id, username=username, email=email)
        self._users[user.user_id] = user
        self._next_id += 1
        return user

    def get(self, user_id: int) -> User | None:
        """Look up a user by id."""
        return self._users.get(user_id)


class UserNotFoundError(Exception):
    """Raised when a request references a user id that doesn't exist."""


class Mailer(Protocol):
    """The slice of a mail service ``SendWelcomeEmailHandler`` needs."""

    async def send(self, to: str, subject: str, body: str) -> None:
        """Send an email."""
        ...


class ConsoleMailer:
    """The default ``Mailer``: prints instead of sending. Good enough for a demo."""

    async def send(self, to: str, subject: str, body: str) -> None:
        """Print the email instead of sending it."""
        print(f"[mail] to={to} subject={subject!r} body={body!r}", file=sys.stderr)


# ---- A leaf handler: no dependency that dispatches anything ----


@dataclass
class GetUser(Request[User]):
    """Look up a user by id; responds with the stored User."""

    user_id: int


class GetUserHandler(RequestHandler[GetUser]):
    """Looks up existing users. The simplest possible handler to test."""

    def __init__(self, repository: UserRepository) -> None:
        self._repository = repository

    async def __call__(self, request: GetUser) -> User:
        user = self._repository.get(request.user_id)
        if user is None:
            raise UserNotFoundError(f"No user with id {request.user_id}")
        return user


# ---- A leaf handler with a different dependency shape ----


@dataclass
class SendWelcomeEmail(Request[None]):
    """Send a welcome email to a newly registered user."""

    user_id: int
    email: str


class SendWelcomeEmailHandler(RequestHandler[SendWelcomeEmail]):
    """Sends the welcome email. A leaf: it dispatches nothing further."""

    def __init__(self, mailer: Mailer) -> None:
        self._mailer = mailer

    async def __call__(self, request: SendWelcomeEmail) -> None:
        await self._mailer.send(
            to=request.email, subject="Welcome!", body=f"Welcome, user {request.user_id}!"
        )


# ---- A composing handler: dispatches through an injected sender ----


class Sender(Protocol):
    """The slice of the mediator a composing handler needs: dispatch, nothing else.

    ``Mediator`` satisfies this structurally, and so does ``LateBoundSender``. Depending
    on this narrow interface — rather than the concrete ``Mediator`` — is what lets the
    handler be constructed before the mediator exists, and swapped for a fake in a test.
    """

    async def send(self, request: Request[ResponseT]) -> ResponseT:
        """Dispatch a request to its handler and await the typed response."""
        ...


@dataclass
class RegisterUser(Request[User]):
    """Register a user, then send them a welcome email."""

    username: str
    email: str


class RegisterUserHandler(RequestHandler[RegisterUser]):
    """Creates a user, then dispatches ``SendWelcomeEmail`` through the injected sender.

    This is the handler ``test_composition.py`` fakes the mediator for: testing it
    doesn't require wiring up ``SendWelcomeEmailHandler`` or a real mailer at all.
    """

    def __init__(self, sender: Sender, repository: UserRepository) -> None:
        self._sender = sender
        self._repository = repository

    async def __call__(self, request: RegisterUser) -> User:
        user = self._repository.create(request.username, request.email)
        await self._sender.send(SendWelcomeEmail(user_id=user.user_id, email=user.email))
        return user


class LateBoundSender:
    """A ``Sender`` registered before the mediator exists, then ``bind`` once it does.

    ``RegisterUserHandler`` depends on ``Sender``, so this can go into the same
    ``Services`` the mediator is built from. Immediately after constructing the
    mediator, ``build_mediator`` calls ``bind`` to close the loop.
    """

    def __init__(self) -> None:
        self._mediator: Mediator | None = None

    def bind(self, mediator: Mediator) -> None:
        """Attach the mediator that dispatches will forward to."""
        self._mediator = mediator

    async def send(self, request: Request[ResponseT]) -> ResponseT:
        """Forward a request to the bound mediator and await its response."""
        if self._mediator is None:
            raise RuntimeError("LateBoundSender.send called before bind()")
        return await self._mediator.send(request)


# ---- A handler whose behavior varies by constructor — the registry-gotcha fix ----


@dataclass
class GreetResponse:
    """The greeting a ``GreetHandler`` produces."""

    message: str


@dataclass
class Greet(Request[GreetResponse]):
    """Greet someone by name."""

    name: str


class GreetHandler(RequestHandler[Greet]):
    """Greets by name, with a configurable greeting.

    Two tests wanting two different greetings construct two instances of *this* class
    with different arguments — they never define a second ``RequestHandler[Greet]``.
    See ``test_registry_gotcha.py``.
    """

    def __init__(self, greeting: str = "Hello") -> None:
        self._greeting = greeting

    async def __call__(self, request: Greet) -> GreetResponse:
        return GreetResponse(message=f"{self._greeting}, {request.name}!")


# ---- Wiring: only test_integration.py and the demo below need this ----


def build_mediator(
    repository: UserRepository | None = None, mailer: Mailer | None = None
) -> Mediator:
    """Wire every handler above onto one mediator."""
    repository = repository if repository is not None else UserRepository()
    mailer = mailer if mailer is not None else ConsoleMailer()
    sender = LateBoundSender()

    services = Services()
    services.add(GetUserHandler(repository))
    services.add(SendWelcomeEmailHandler(mailer))
    services.add(RegisterUserHandler(sender, repository))
    services.add(GreetHandler())

    mediator = Mediator(services.provider())
    sender.bind(mediator)
    return mediator
