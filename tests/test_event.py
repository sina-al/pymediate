"""Tests for Event, the sync EventHandler, and Mediator.publish."""

from dataclasses import dataclass

import pytest

from pymediate._internal import registry
from pymediate.sync import (
    Event,
    EventHandler,
    InvalidEventTypeError,
    InvalidHandlerSignatureError,
    Mediator,
    ServiceNotFoundError,
    Services,
)


def test_event_handler_extracts_event_type() -> None:
    """Test that EventHandler subclasses record their event type."""

    class Ping(Event):
        pass

    class PingHandler(EventHandler[Ping]):
        def __call__(self, event: Ping) -> None:
            pass

    assert PingHandler.get_event_type() is Ping


def test_multiple_handlers_may_register_for_one_event() -> None:
    """Test that N handlers per event type is allowed, unlike request handlers."""

    class Ping(Event):
        pass

    class First(EventHandler[Ping]):
        def __call__(self, event: Ping) -> None:
            pass

    class Second(EventHandler[Ping]):
        def __call__(self, event: Ping) -> None:
            pass

    assert registry.get_event_handler_classes(Ping) == (First, Second)
    assert registry.has_event_handlers(Ping)
    assert Ping in registry.get_all_event_types()


def test_publish_invokes_all_handlers_in_registration_order() -> None:
    """Test that publish runs every subscriber in registration order."""

    @dataclass
    class OrderPlaced(Event):
        order_id: int

    calls: list[str] = []

    class SendConfirmation(EventHandler[OrderPlaced]):
        def __call__(self, event: OrderPlaced) -> None:
            calls.append(f"confirm:{event.order_id}")

    class UpdateAnalytics(EventHandler[OrderPlaced]):
        def __call__(self, event: OrderPlaced) -> None:
            calls.append(f"analytics:{event.order_id}")

    services = Services()
    services.add(SendConfirmation()).add(UpdateAnalytics())
    mediator = Mediator(services.provider())

    mediator.publish(OrderPlaced(order_id=42))

    assert calls == ["confirm:42", "analytics:42"]


def test_publish_with_zero_handlers_is_a_no_op() -> None:
    """Test that publishing an event nobody subscribed to succeeds silently."""

    class NobodyListens(Event):
        pass

    mediator = Mediator(Services().provider())
    mediator.publish(NobodyListens())  # Must not raise.


def test_publish_dispatches_on_exact_event_type() -> None:
    """Test that a subscriber to a base event does not receive derived events."""

    @dataclass
    class OrderPlaced(Event):
        order_id: int

    @dataclass
    class RushOrderPlaced(OrderPlaced):
        pass

    calls: list[int] = []

    class BaseSubscriber(EventHandler[OrderPlaced]):
        def __call__(self, event: OrderPlaced) -> None:
            calls.append(event.order_id)

    services = Services()
    services.add(BaseSubscriber())
    mediator = Mediator(services.provider())

    mediator.publish(RushOrderPlaced(order_id=1))

    assert calls == []


def test_publish_runs_all_handlers_and_raises_exception_group() -> None:
    """Test that one failing handler doesn't stop the others."""

    class Boom(Event):
        pass

    ran: list[str] = []

    class FailsFirst(EventHandler[Boom]):
        def __call__(self, event: Boom) -> None:
            ran.append("first")
            raise ValueError("first failed")

    class StillRuns(EventHandler[Boom]):
        def __call__(self, event: Boom) -> None:
            ran.append("second")

    class FailsLast(EventHandler[Boom]):
        def __call__(self, event: Boom) -> None:
            ran.append("third")
            raise ConnectionError("third failed")

    services = Services()
    services.add(FailsFirst()).add(StillRuns()).add(FailsLast())
    mediator = Mediator(services.provider())

    with pytest.raises(ExceptionGroup) as excinfo:
        mediator.publish(Boom())

    assert ran == ["first", "second", "third"]
    assert "2 of 3 event handlers raised while publishing Boom" in str(excinfo.value)
    assert {type(exc) for exc in excinfo.value.exceptions} == {ValueError, ConnectionError}


def test_publish_exception_group_supports_except_star() -> None:
    """Test that publish failures can be handled selectively with except*."""

    class Boom(Event):
        pass

    class Fails(EventHandler[Boom]):
        def __call__(self, event: Boom) -> None:
            raise ValueError("boom")

    services = Services()
    services.add(Fails())
    mediator = Mediator(services.provider())

    caught: list[Exception] = []
    try:
        mediator.publish(Boom())
    except* ValueError as group:
        caught.extend(group.exceptions)

    assert len(caught) == 1


def test_publish_fails_fast_when_a_handler_instance_is_missing() -> None:
    """Test that a resolution failure propagates before any handler runs."""

    class HalfWired(Event):
        pass

    ran: list[str] = []

    class Wired(EventHandler[HalfWired]):
        def __call__(self, event: HalfWired) -> None:
            ran.append("wired")

    class NotWired(EventHandler[HalfWired]):
        def __call__(self, event: HalfWired) -> None:
            ran.append("not-wired")

    services = Services()
    services.add(Wired())  # NotWired instance deliberately not registered.
    mediator = Mediator(services.provider())

    with pytest.raises(ServiceNotFoundError):
        mediator.publish(HalfWired())

    assert ran == []  # No partial delivery.


def test_event_handler_rejects_non_event_type_parameter() -> None:
    """Test that EventHandler[NotAnEvent] raises at class definition."""

    class NotAnEvent:
        pass

    with pytest.raises(InvalidEventTypeError, match="must inherit from Event"):

        class Bad(EventHandler[NotAnEvent]):  # type: ignore[type-var]
            def __call__(self, event: NotAnEvent) -> None:
                pass


def test_event_handler_requires_none_return_annotation() -> None:
    """Test that a non-None return annotation is rejected with a teaching message."""

    class Ping(Event):
        pass

    with pytest.raises(InvalidHandlerSignatureError, match="must be annotated to return None"):

        class Bad(EventHandler[Ping]):
            def __call__(self, event: Ping) -> int:
                return 1


def test_event_handler_rejects_base_class_parameter_annotation() -> None:
    """Test that the exact-annotation contract (ADR 0004) applies to events too."""

    class BaseEvent(Event):
        pass

    class DerivedEvent(BaseEvent):
        pass

    with pytest.raises(
        InvalidHandlerSignatureError,
        match="exact event class.*a base class of DerivedEvent",
    ):

        class Bad(EventHandler[DerivedEvent]):
            def __call__(self, event: BaseEvent) -> None:
                pass


def test_event_handler_requires_call_method() -> None:
    """Test that an EventHandler subclass without a __call__ override is rejected."""

    class Ping(Event):
        pass

    with pytest.raises(InvalidHandlerSignatureError, match="must implement __call__"):

        class Bad(EventHandler[Ping]):
            pass


def test_sync_event_handler_rejects_async_call() -> None:
    """Test that the sync EventHandler rejects an async __call__."""

    class Ping(Event):
        pass

    with pytest.raises(InvalidHandlerSignatureError, match="__call__ must be sync"):

        class Bad(EventHandler[Ping]):
            async def __call__(self, event: Ping) -> None:
                pass


def test_registry_stats_include_event_handlers() -> None:
    """Test that registry stats report event handler registrations."""

    class Ping(Event):
        pass

    class PingHandler(EventHandler[Ping]):
        def __call__(self, event: Ping) -> None:
            pass

    stats = registry.get_registry_stats()
    assert stats["event_handler_count"] >= 1


def test_clear_handler_registry_clears_event_registrations() -> None:
    """Test that the test-isolation clear covers event handlers too."""

    class Ping(Event):
        pass

    class PingHandler(EventHandler[Ping]):
        def __call__(self, event: Ping) -> None:
            pass

    assert registry.has_event_handlers(Ping)
    registry.clear_handler_registry()
    assert not registry.has_event_handlers(Ping)
    assert registry.get_event_handler_classes(Ping) == ()
