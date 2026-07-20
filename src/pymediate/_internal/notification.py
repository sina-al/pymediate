"""Shared base logic for both sync and async notification handlers.

This module provides NotificationHandlerBaseMixin, which contains the type extraction,
validation, and registration logic common between sync and async notification handlers.
It reuses the signature validator from handler.py; the notification-specific differences
are the None return contract and N-allowed registration.
"""

from typing import Any, get_args, get_origin

from .. import errors
from . import registry
from .handler import _qualified_name, _validate_call_signature


class NotificationHandlerBaseMixin[NotificationT]:
    """Mixin providing shared logic for both sync and async notification handlers.

    This mixin contains the type extraction, validation, and registration logic
    that is common between synchronous and asynchronous notification handlers.

    Type Parameters:
        NotificationT: The type of notification this handler subscribes to.

    Attributes:
        _notification_type: Class-level attribute storing the notification type.
    """

    _notification_type: type | None = None
    _is_async: bool = False  # Set by subclass

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Extract the notification type, validate the handler signature, and register.

        This hook is automatically called when a new NotificationHandler subclass is
        defined. It extracts the notification type from NotificationHandler[NotificationType],
        validates the __call__ signature (exact notification annotation, None return),
        and appends the handler to the notification's registration list - any number of
        handlers may register for the same notification type. The registry is shared by
        the synchronous and asynchronous handler bases; callers must keep every
        handler for one exact notification type in the same execution model.

        Args:
            **kwargs: Additional keyword arguments passed to parent __init_subclass__.

        Raises:
            InvalidNotificationTypeError: If the notification type doesn't inherit from
                Notification.
            InvalidHandlerSignatureError: If the __call__ signature is invalid,
                including a return annotation other than None.
        """
        super().__init_subclass__(**kwargs)

        cls._notification_type = None

        # Extract notification type from NotificationHandler[NotificationType]; find the base whose
        # origin is a NotificationHandler-like class (NotificationHandlerBaseMixin in its mro).
        orig_bases = getattr(cls, "__orig_bases__", ())
        for base in orig_bases:
            origin = get_origin(base)
            if origin and NotificationHandlerBaseMixin in getattr(origin, "__mro__", []):
                args = get_args(base)
                if args:
                    cls._notification_type = args[0]
                    break

        if cls._notification_type is None:
            return

        # Imported lazily: pymediate.notification imports this module at import time.
        from ..notification import Notification

        if not (
            isinstance(cls._notification_type, type)
            and issubclass(cls._notification_type, Notification)
        ):
            # Skip the base classes themselves, whose type argument is a TypeVar.
            if cls.__name__ not in ("NotificationHandler", "NotificationHandlerBaseMixin"):
                raise errors.InvalidNotificationTypeError(cls._notification_type)
            return

        try:
            _validate_call_signature(
                cls,
                cls._notification_type,
                type(None),
                is_async=cls._is_async,
                kind="notification",
                declaration_name="NotificationHandler",
            )
        except errors.ResponseTypeMismatchError as exc:
            raise errors.InvalidHandlerSignatureError(
                cls,
                "__call__ must be annotated to return None - notification handlers produce "
                f"no response, got {_qualified_name(exc.actual_type)}",
            ) from None

        registry.register_notification_handler(cls._notification_type, cls)

    @classmethod
    def get_notification_type(cls) -> type | None:
        """Get the notification type this handler subscribes to.

        Returns:
            The notification type class that this handler is designed to process,
            or None if no notification type was specified.
        """
        return cls._notification_type
