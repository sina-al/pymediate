"""Boundary 3: verify request routing through a configured ``Mediator``.

These tests check the registration between ``RegisterUserHandler`` and
``SendWelcomeEmailHandler`` in addition to each handler's behavior.
"""

from app import GetUser, RegisterUser, build_mediator


class RecordingMailer:
    """Record messages instead of sending them."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str, str]] = []

    async def send(self, to: str, subject: str, body: str) -> None:
        self.sent.append((to, subject, body))


async def test_register_user_reaches_the_real_welcome_email_handler() -> None:
    mailer = RecordingMailer()
    mediator = build_mediator(mailer=mailer)

    user = await mediator.send(RegisterUser(username="alice", email="alice@example.com"))

    # This checks the route configured by build_mediator:
    # RegisterUser -> RegisterUserHandler -> SendWelcomeEmail -> SendWelcomeEmailHandler.
    assert mailer.sent == [("alice@example.com", "Welcome!", f"Welcome, user {user.user_id}!")]


async def test_registered_user_is_then_gettable() -> None:
    mediator = build_mediator()

    registered = await mediator.send(RegisterUser(username="bob", email="bob@example.com"))
    found = await mediator.send(GetUser(user_id=registered.user_id))

    assert found == registered
