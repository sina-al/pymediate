"""Layer 2: faking the mediator, for a handler that dispatches through one.

``RegisterUserHandler`` depends on ``Sender`` — the narrow slice of the mediator it
actually uses — not the concrete ``Mediator``. That's what makes this test possible
without wiring up ``SendWelcomeEmailHandler``, a real mailer, or a container at all:
a `FakeSender` that just records what it was asked to send is enough.
"""

from typing import TypeVar, cast

from pymediate import Request

from app import RegisterUser, RegisterUserHandler, SendWelcomeEmail, UserRepository

ResponseT = TypeVar("ResponseT")


class FakeSender:
    """A fake ``Sender`` — records every request it was asked to dispatch, answers nothing.

    Every request this example dispatches through a ``Sender`` responds with ``None``
    (``SendWelcomeEmail`` is a ``Request[None]``), so the ``cast`` below documents a
    real gap rather than papering over one: a fake covering a wider ``Sender`` would
    need a way to supply canned responses per request type instead.
    """

    def __init__(self) -> None:
        self.sent: list[Request[object]] = []

    async def send(self, request: Request[ResponseT]) -> ResponseT:
        self.sent.append(request)
        return cast(ResponseT, None)


async def test_register_user_dispatches_a_welcome_email() -> None:
    sender = FakeSender()
    handler = RegisterUserHandler(sender, UserRepository())

    await handler(RegisterUser(username="alice", email="alice@example.com"))

    assert len(sender.sent) == 1
    sent = sender.sent[0]
    assert isinstance(sent, SendWelcomeEmail)
    assert sent.email == "alice@example.com"


async def test_register_user_returns_the_created_user() -> None:
    handler = RegisterUserHandler(FakeSender(), UserRepository())

    user = await handler(RegisterUser(username="bob", email="bob@example.com"))

    assert user.username == "bob"
    assert user.user_id == 1
