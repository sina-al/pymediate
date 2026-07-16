"""Layer 1: handlers tested directly, as plain callables. No mediator in sight.

This is the fastest and most common test in the suite: construct the handler with a
fake dependency, call it, assert on the response. A handler is `__init__` plus
`__call__` — nothing about testing it needs PyMediate at all.
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
    """A fake mail service — records what it was asked to send, sends nothing."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str, str]] = []

    async def send(self, to: str, subject: str, body: str) -> None:
        self.sent.append((to, subject, body))


async def test_get_user_handler_returns_the_stored_user() -> None:
    repository = UserRepository()
    repository.create(username="alice", email="alice@example.com")
    handler = GetUserHandler(repository)

    user = await handler(GetUser(user_id=1))

    assert user.username == "alice"


async def test_get_user_handler_raises_for_an_unknown_id() -> None:
    handler = GetUserHandler(UserRepository())

    with pytest.raises(UserNotFoundError):
        await handler(GetUser(user_id=999))


async def test_send_welcome_email_handler_sends_through_the_mailer() -> None:
    mailer = FakeMailer()
    handler = SendWelcomeEmailHandler(mailer)

    await handler(SendWelcomeEmail(user_id=1, email="alice@example.com"))

    assert mailer.sent == [("alice@example.com", "Welcome!", "Welcome, user 1!")]
