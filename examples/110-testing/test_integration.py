"""Layer 3: an end-to-end-ish test through a real Mediator.

Reserve this layer for what layers 1 and 2 structurally can't check: that the pieces
are wired together correctly — ``RegisterUser`` really is routed to
``RegisterUserHandler``, which really does reach a real ``SendWelcomeEmailHandler``
through the mediator, not a fake standing in for it. Contrast the cost: this test
needs a container and two collaborating handlers built just to answer one question
that `test_handlers.py` and `test_composition.py` each answer more cheaply on their own.
"""

from app import GetUser, RegisterUser, build_mediator
from test_handlers import FakeMailer


async def test_register_user_reaches_the_real_welcome_email_handler() -> None:
    mailer = FakeMailer()
    mediator = build_mediator(mailer=mailer)

    user = await mediator.send(RegisterUser(username="alice", email="alice@example.com"))

    # Nothing here reaches into SendWelcomeEmailHandler directly — this is the mediator
    # actually routing RegisterUser -> RegisterUserHandler -> SendWelcomeEmail ->
    # SendWelcomeEmailHandler, exactly as build_mediator wired it.
    assert mailer.sent == [("alice@example.com", "Welcome!", f"Welcome, user {user.user_id}!")]


async def test_registered_user_is_then_gettable() -> None:
    mediator = build_mediator()

    registered = await mediator.send(RegisterUser(username="bob", email="bob@example.com"))
    found = await mediator.send(GetUser(user_id=registered.user_id))

    assert found == registered
