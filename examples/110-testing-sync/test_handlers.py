"""Boundary 1: construct handlers with test dependencies and call them directly.

These tests check handler results and direct dependency interactions without configuring a
mediator.
"""

import pytest

from app import (
    GetUser,
    GetUserHandler,
    SendWelcomeEmail,
    SendWelcomeEmailHandler,
    UserNotFoundError,
    UserRepository,
)


class FakeMailer:
    """Record messages instead of sending them."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str, str]] = []

    def send(self, to: str, subject: str, body: str) -> None:
        self.sent.append((to, subject, body))


def test_get_user_handler_returns_the_stored_user() -> None:
    repository = UserRepository()
    repository.create(username="alice", email="alice@example.com")
    handler = GetUserHandler(repository)

    user = handler(GetUser(user_id=1))

    assert user.username == "alice"


def test_get_user_handler_raises_for_an_unknown_id() -> None:
    handler = GetUserHandler(UserRepository())

    with pytest.raises(UserNotFoundError):
        handler(GetUser(user_id=999))


def test_send_welcome_email_handler_sends_through_the_mailer() -> None:
    mailer = FakeMailer()
    handler = SendWelcomeEmailHandler(mailer)

    handler(SendWelcomeEmail(user_id=1, email="alice@example.com"))

    assert mailer.sent == [("alice@example.com", "Welcome!", "Welcome, user 1!")]
