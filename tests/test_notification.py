"""Tests for Notification, the sync NotificationHandler, and Mediator.publish."""

from dataclasses import dataclass

import pytest

from pymediate._internal import registry
from pymediate.sync import (
    InvalidHandlerSignatureError,
    InvalidNotificationTypeError,
    Mediator,
    Notification,
    NotificationHandler,
    ServiceNotFoundError,
    Services,
)


def test_notification_handler_extracts_notification_type() -> None:
    """Test that NotificationHandler subclasses record their notification type."""

    class Ping(Notification):
        pass

    class PingHandler(NotificationHandler[Ping]):
        def __call__(self, notification: Ping) -> None:
            pass

    assert PingHandler.get_notification_type() is Ping


def test_multiple_handlers_may_register_for_one_notification() -> None:
    """Test that N handlers per notification type is allowed, unlike request handlers."""

    class Ping(Notification):
        pass

    class First(NotificationHandler[Ping]):
        def __call__(self, notification: Ping) -> None:
            pass

    class Second(NotificationHandler[Ping]):
        def __call__(self, notification: Ping) -> None:
            pass

    assert registry.get_notification_handler_classes(Ping) == (First, Second)
    assert registry.has_notification_handlers(Ping)
    assert Ping in registry.get_all_notification_types()


def test_publish_invokes_all_handlers_in_registration_order() -> None:
    """Test that publish runs every subscriber in registration order."""

    @dataclass
    class OrderPlaced(Notification):
        order_id: int

    calls: list[str] = []

    class SendConfirmation(NotificationHandler[OrderPlaced]):
        def __call__(self, notification: OrderPlaced) -> None:
            calls.append(f"confirm:{notification.order_id}")

    class UpdateAnalytics(NotificationHandler[OrderPlaced]):
        def __call__(self, notification: OrderPlaced) -> None:
            calls.append(f"analytics:{notification.order_id}")

    services = Services()
    services.add(SendConfirmation()).add(UpdateAnalytics())
    mediator = Mediator(services.provider())

    mediator.publish(OrderPlaced(order_id=42))

    assert calls == ["confirm:42", "analytics:42"]


def test_publish_with_zero_handlers_is_a_no_op() -> None:
    """Test that publishing a notification nobody subscribed to succeeds silently."""

    class NobodyListens(Notification):
        pass

    mediator = Mediator(Services().provider())
    mediator.publish(NobodyListens())  # Must not raise.


def test_publish_dispatches_on_exact_notification_type() -> None:
    """Test that a subscriber to a base notification does not receive derived notifications."""

    @dataclass
    class OrderPlaced(Notification):
        order_id: int

    @dataclass
    class RushOrderPlaced(OrderPlaced):
        pass

    calls: list[int] = []

    class BaseSubscriber(NotificationHandler[OrderPlaced]):
        def __call__(self, notification: OrderPlaced) -> None:
            calls.append(notification.order_id)

    services = Services()
    services.add(BaseSubscriber())
    mediator = Mediator(services.provider())

    mediator.publish(RushOrderPlaced(order_id=1))

    assert calls == []


def test_publish_runs_all_handlers_and_raises_exception_group() -> None:
    """Test that one failing handler doesn't stop the others."""

    class Boom(Notification):
        pass

    ran: list[str] = []

    class FailsFirst(NotificationHandler[Boom]):
        def __call__(self, notification: Boom) -> None:
            ran.append("first")
            raise ValueError("first failed")

    class StillRuns(NotificationHandler[Boom]):
        def __call__(self, notification: Boom) -> None:
            ran.append("second")

    class FailsLast(NotificationHandler[Boom]):
        def __call__(self, notification: Boom) -> None:
            ran.append("third")
            raise ConnectionError("third failed")

    services = Services()
    services.add(FailsFirst()).add(StillRuns()).add(FailsLast())
    mediator = Mediator(services.provider())

    with pytest.raises(ExceptionGroup) as excinfo:
        mediator.publish(Boom())

    assert ran == ["first", "second", "third"]
    assert "2 of 3 notification handlers raised while publishing Boom" in str(excinfo.value)
    assert {type(exc) for exc in excinfo.value.exceptions} == {ValueError, ConnectionError}


def test_publish_exception_group_supports_except_star() -> None:
    """Test that publish failures can be handled selectively with except*."""

    class Boom(Notification):
        pass

    class Fails(NotificationHandler[Boom]):
        def __call__(self, notification: Boom) -> None:
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

    class HalfWired(Notification):
        pass

    ran: list[str] = []

    class Wired(NotificationHandler[HalfWired]):
        def __call__(self, notification: HalfWired) -> None:
            ran.append("wired")

    class NotWired(NotificationHandler[HalfWired]):
        def __call__(self, notification: HalfWired) -> None:
            ran.append("not-wired")

    services = Services()
    services.add(Wired())  # NotWired instance deliberately not registered.
    mediator = Mediator(services.provider())

    with pytest.raises(ServiceNotFoundError):
        mediator.publish(HalfWired())

    assert ran == []  # No partial delivery.


def test_notification_handler_rejects_non_notification_type_parameter() -> None:
    """Test that NotificationHandler[NotANotification] raises at class definition."""

    class NotANotification:
        pass

    with pytest.raises(InvalidNotificationTypeError, match="must inherit from Notification"):

        class Bad(NotificationHandler[NotANotification]):  # type: ignore[type-var]
            def __call__(self, notification: NotANotification) -> None:
                pass


def test_notification_handler_requires_none_return_annotation() -> None:
    """Test that a non-None return annotation is rejected with a teaching message."""

    class Ping(Notification):
        pass

    with pytest.raises(InvalidHandlerSignatureError, match="must be annotated to return None"):

        class Bad(NotificationHandler[Ping]):
            def __call__(self, notification: Ping) -> int:
                return 1


def test_notification_handler_rejects_base_class_parameter_annotation() -> None:
    """Test that the exact-annotation contract (ADR 0004) applies to notifications too."""

    class BaseNotification(Notification):
        pass

    class DerivedNotification(BaseNotification):
        pass

    with pytest.raises(
        InvalidHandlerSignatureError,
        match="exact notification class.*a base class of DerivedNotification",
    ):

        class Bad(NotificationHandler[DerivedNotification]):
            def __call__(self, notification: BaseNotification) -> None:
                pass


def test_notification_handler_requires_call_method() -> None:
    """Test that a NotificationHandler subclass without a __call__ override is rejected."""

    class Ping(Notification):
        pass

    with pytest.raises(InvalidHandlerSignatureError, match="must implement __call__"):

        class Bad(NotificationHandler[Ping]):
            pass


def test_sync_notification_handler_rejects_async_call() -> None:
    """Test that the sync NotificationHandler rejects an async __call__."""

    class Ping(Notification):
        pass

    with pytest.raises(InvalidHandlerSignatureError, match="__call__ must be sync"):

        class Bad(NotificationHandler[Ping]):
            async def __call__(self, notification: Ping) -> None:
                pass


def test_registry_stats_include_notification_handlers() -> None:
    """Test that registry stats report notification handler registrations."""

    class Ping(Notification):
        pass

    class PingHandler(NotificationHandler[Ping]):
        def __call__(self, notification: Ping) -> None:
            pass

    stats = registry.get_registry_stats()
    assert stats["notification_handler_count"] >= 1


def test_clear_handler_registry_clears_notification_registrations() -> None:
    """Test that the test-isolation clear covers notification handlers too."""

    class Ping(Notification):
        pass

    class PingHandler(NotificationHandler[Ping]):
        def __call__(self, notification: Ping) -> None:
            pass

    assert registry.has_notification_handlers(Ping)
    registry.clear_handler_registry()
    assert not registry.has_notification_handlers(Ping)
    assert registry.get_notification_handler_classes(Ping) == ()
