"""Handlers must validate and dispatch under `from __future__ import annotations`.

PEP 563 stores `__call__` annotations as strings, so signature validation has to
resolve them before comparing against the expected request/response types. These
types are declared at module level because string annotations can only be resolved
against a handler method's module globals, not a test function's locals.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest

from pymediate import (
    Event,
    Handler,
    InvalidHandlerSignatureError,
    Mediator,
    Request,
    ResponseTypeMismatchError,
)
from pymediate.aio import Handler as AsyncHandler
from pymediate.aio import Mediator as AsyncMediator
from pymediate.service import Services


@dataclass
class UserCreated:
    user_id: int


@dataclass
class CreateUser(Request[UserCreated]):
    name: str


@dataclass
class OtherRequest(Request[UserCreated]):
    pass


def test_sync_handler_defines_and_dispatches_under_future_annotations() -> None:
    class CreateUserHandler(Handler[CreateUser]):
        def __call__(self, request: CreateUser) -> UserCreated:
            return UserCreated(user_id=1)

    assert CreateUserHandler._request_type is CreateUser
    assert CreateUserHandler._response_type is UserCreated

    services = Services()
    services.add(CreateUserHandler())
    mediator = Mediator(services.provider())

    assert mediator.send(CreateUser(name="alice")) == UserCreated(user_id=1)


def test_async_handler_defines_and_dispatches_under_future_annotations() -> None:
    class CreateUserHandler(AsyncHandler[CreateUser]):
        async def __call__(self, request: CreateUser) -> UserCreated:
            return UserCreated(user_id=2)

    services = Services()
    services.add(CreateUserHandler())
    mediator = AsyncMediator(services.provider())

    assert asyncio.run(mediator.send(CreateUser(name="bob"))) == UserCreated(user_id=2)


def test_wrong_parameter_type_still_rejected_under_future_annotations() -> None:
    with pytest.raises(InvalidHandlerSignatureError, match="exact request class"):

        class BadHandler(Handler[CreateUser]):
            def __call__(self, request: OtherRequest) -> UserCreated:
                return UserCreated(user_id=1)


def test_wrong_return_type_still_rejected_under_future_annotations() -> None:
    with pytest.raises(ResponseTypeMismatchError):

        class BadHandler(Handler[OtherRequest]):
            def __call__(self, request: OtherRequest) -> int:
                return 1


@dataclass
class UserRegistered(Event):
    user_id: int


def test_event_handler_defines_and_publishes_under_future_annotations() -> None:
    from pymediate import EventHandler, Mediator

    calls: list[int] = []

    class WelcomeSubscriber(EventHandler[UserRegistered]):
        def __call__(self, event: UserRegistered) -> None:
            calls.append(event.user_id)

    services = Services()
    services.add(WelcomeSubscriber())
    mediator = Mediator(services.provider())

    mediator.publish(UserRegistered(user_id=7))
    assert calls == [7]


def test_event_handler_wrong_return_still_rejected_under_future_annotations() -> None:
    from pymediate import EventHandler

    with pytest.raises(InvalidHandlerSignatureError, match="must be annotated to return None"):

        class BadSubscriber(EventHandler[UserRegistered]):
            def __call__(self, event: UserRegistered) -> int:
                return 1
