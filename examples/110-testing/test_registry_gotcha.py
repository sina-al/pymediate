"""The handler registry is process-global, not per-test.

Each ``RequestHandler[RequestT]`` subclass registers itself against its request type
the moment the class body executes — in one registry shared by the whole process, not
per ``Services`` instance. Defining a second handler for a request type that already
has one raises ``HandlerAlreadyRegisteredError`` across
two tests in the same file as it does across two files in the same run.
"""

import pytest
from pymediate import HandlerAlreadyRegisteredError, RequestHandler

from app import Greet, GreetHandler, GreetResponse


def test_redefining_the_handler_class_raises() -> None:
    # GreetHandler is already registered for Greet (app.py imported it at collection
    # time). Defining a second RequestHandler[Greet] to change one test's
    # greeting — raises at the `class` statement itself.
    with pytest.raises(HandlerAlreadyRegisteredError, match="Greet"):

        class AnotherGreetHandler(RequestHandler[Greet]):
            async def __call__(self, request: Greet) -> GreetResponse:
                return GreetResponse(message=f"Bonjour, {request.name}!")


async def test_the_fix_is_varying_the_constructor_not_the_class() -> None:
    # Two behaviors, one class: GreetHandler takes its greeting as a constructor
    # argument, so two tests wanting two different greetings construct two instances
    # instead of defining two classes.
    formal = GreetHandler(greeting="Good day")
    casual = GreetHandler(greeting="Hey")

    formal_response = await formal(Greet(name="Alice"))
    casual_response = await casual(Greet(name="Bob"))

    assert formal_response.message == "Good day, Alice!"
    assert casual_response.message == "Hey, Bob!"


async def test_the_default_greeting_still_works() -> None:
    # The same GreetHandler class, a third instance, a third greeting — no redefinition.
    handler = GreetHandler()

    response = await handler(Greet(name="Carol"))

    assert response.message == "Hello, Carol!"
