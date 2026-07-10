"""Shared base logic for both sync and async event handlers.

This module provides EventHandlerBaseMixin, which contains the type extraction,
validation, and registration logic common between sync and async event handlers.
It reuses the signature validator from handler.py; the event-specific differences
are the None return contract and N-allowed registration.
"""

from typing import Any, get_args, get_origin

from .. import errors
from . import registry
from .handler import _qualified_name, _validate_call_signature


class EventHandlerBaseMixin[EventT]:
    """Mixin providing shared logic for both sync and async event handlers.

    This mixin contains the type extraction, validation, and registration logic
    that is common between synchronous and asynchronous event handlers.

    Type Parameters:
        EventT: The type of event this handler subscribes to.

    Attributes:
        _event_type: Class-level attribute storing the event type.
    """

    _event_type: type | None = None
    _is_async: bool = False  # Set by subclass

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Extract the event type, validate the handler signature, and register.

        This hook is automatically called when a new EventHandler subclass is
        defined. It extracts the event type from EventHandler[EventType],
        validates the __call__ signature (exact event annotation, None return),
        and appends the handler to the event's registration list - any number of
        handlers may register for the same event type.

        Args:
            **kwargs: Additional keyword arguments passed to parent __init_subclass__.

        Raises:
            InvalidEventTypeError: If the event type doesn't inherit from Event.
            InvalidHandlerSignatureError: If the __call__ signature is invalid,
                including a return annotation other than None.
        """
        super().__init_subclass__(**kwargs)

        cls._event_type = None

        # Extract event type from EventHandler[EventType]; find the base whose
        # origin is an EventHandler-like class (EventHandlerBaseMixin in its mro).
        orig_bases = getattr(cls, "__orig_bases__", ())
        for base in orig_bases:
            origin = get_origin(base)
            if origin and EventHandlerBaseMixin in getattr(origin, "__mro__", []):
                args = get_args(base)
                if args:
                    cls._event_type = args[0]
                    break

        if cls._event_type is None:
            return

        # Imported lazily: pymediate.event imports this module at import time.
        from ..event import Event

        if not (isinstance(cls._event_type, type) and issubclass(cls._event_type, Event)):
            # Skip the base classes themselves, whose type argument is a TypeVar.
            if cls.__name__ not in ("EventHandler", "EventHandlerBaseMixin"):
                raise errors.InvalidEventTypeError(cls._event_type)
            return

        try:
            _validate_call_signature(
                cls,
                cls._event_type,
                type(None),
                is_async=cls._is_async,
                kind="event",
                declaration_name="EventHandler",
            )
        except errors.ResponseTypeMismatchError as exc:
            raise errors.InvalidHandlerSignatureError(
                cls,
                "__call__ must be annotated to return None - event handlers produce "
                f"no response, got {_qualified_name(exc.actual_type)}",
            ) from None

        registry.register_event_handler(cls._event_type, cls)

    @classmethod
    def get_event_type(cls) -> type | None:
        """Get the event type this handler subscribes to.

        Returns:
            The event type class that this handler is designed to process,
            or None if no event type was specified.
        """
        return cls._event_type
