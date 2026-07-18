"""Boundary 2: replace the sender used by a handler that dispatches another request.

``RegisterUserHandler`` depends on ``Sender`` — the narrow part of the mediator interface it
uses, not the concrete ``Mediator``. The test can therefore record the dispatched
request without configuring ``SendWelcomeEmailHandler``, a mailer, or a container.
"""

from typing import TypeVar, cast

from pymediate import Request

from app import RegisterUser, RegisterUserHandler, SendWelcomeEmail, UserRepository

ResponseT = TypeVar("ResponseT")


class FakeSender:
    """Record each request passed to ``send``.

    Every request this example dispatches through a ``Sender`` responds with ``None``
    (``SendWelcomeEmail`` is a ``Request[None]``), so the ``cast`` below is valid for this
    test implementation. A sender that accepts other request types would need configured
    responses for each type.
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
