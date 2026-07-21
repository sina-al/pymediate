"""Base mixin for mediator implementations (sync and async)."""

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from .. import errors
from . import registry

if TYPE_CHECKING:
    from ..notification import Notification
    from ..request import Request
    from ..service import ServiceProvider


class MediatorMixin:
    """Mixin providing shared logic for both sync and async mediators.

    This mixin contains the common initialization and request processing logic
    that is shared between the synchronous Mediator and asynchronous Mediator.

    The actual send() method is implemented differently in each variant:
    - Synchronous: def send(...) -> ResponseT
    - Asynchronous: async def send(...) -> ResponseT

    Attributes:
        _services: The services instance used to obtain handler and behavior instances.
        _behaviors: The validated pipeline as an ordered tuple of behavior classes.
    """

    _services: "ServiceProvider"
    _behaviors: tuple[type[Any], ...]

    def __init__(
        self,
        services: "ServiceProvider",
        behaviors: "Sequence[type[Any]] | None",
        behavior_base: type,
    ) -> None:
        """Initialize the mediator with a service provider and its pipeline.

        Args:
            services: An object implementing ``ServiceProvider``.
            behaviors: Ordered behavior classes declaring the pipeline, or None
                for an empty pipeline. Validated eagerly - see
                ``_validate_behaviors``.
            behavior_base: The variant's ``PipelineBehavior`` base class that
                every entry must subclass.

        Note:
            The mediator retains this provider for later dispatches. Handler and
            behavior lifetimes therefore follow the provider's policy.
        """
        self._services = services
        self._behaviors = self._validate_behaviors(behaviors, behavior_base)

    def _validate_behaviors(
        self, behaviors: "Sequence[type[Any]] | None", behavior_base: type
    ) -> tuple[type[Any], ...]:
        """Validate the ``behaviors`` sequence once, at mediator construction.

        Every entry must be a class subclassing the variant's ``PipelineBehavior``
        base, must be registered with the service provider (checked via ``has()``),
        and may appear only once. Failing any check raises immediately, so a
        misdeclared pipeline never reaches a dispatch.

        Args:
            behaviors: The ordered behavior classes to validate, or None.
            behavior_base: The variant's ``PipelineBehavior`` base class.

        Returns:
            The validated pipeline as a tuple, empty when behaviors is None.

        Raises:
            InvalidPipelineBehaviorsError: If an entry is not a class, does not
                subclass the variant's ``PipelineBehavior``, is not registered
                with the provider, or is listed more than once.
        """
        if behaviors is None:
            return ()

        validated: list[type[Any]] = []
        for entry in behaviors:
            if not isinstance(entry, type) or not issubclass(entry, behavior_base):
                raise errors.InvalidPipelineBehaviorsError(
                    entry,
                    f"not a {behavior_base.__module__}.{behavior_base.__qualname__} "
                    "subclass - pass the behavior class itself, from the same "
                    "sync/async variant as this mediator",
                )
            if entry in validated:
                raise errors.InvalidPipelineBehaviorsError(
                    entry, "listed more than once in the behaviors sequence"
                )
            if not self._services.has(entry):
                raise errors.InvalidPipelineBehaviorsError(
                    entry,
                    "not registered with the service provider - the mediator "
                    "resolves each listed behavior class through the provider",
                )
            validated.append(entry)
        return tuple(validated)

    def _resolve_handler(self, request: Any) -> Any:
        """Resolve the handler for a request.

        Accepts both `Request` and `StreamRequest` instances - dispatch is keyed by the
        exact request type, which is disjoint between the two, so the same one-handler
        registry resolves either.

        Args:
            request: The request instance to process

        Returns:
            RequestHandler or StreamRequestHandler instance for the request

        Raises:
            HandlerNotFoundError: If no handler is registered for the request type
        """
        # Look up handler type from registry
        request_type = type(request)
        handler_class = registry.get_handler_class(request_type)
        if handler_class is None:
            raise errors.HandlerNotFoundError(request_type, [])

        # Get handler instance
        return self._services.get(handler_class)

    def _resolve_notification_handlers(self, notification: "Notification") -> list[Any]:
        """Resolve every handler instance subscribed to a notification.

        Resolves all handler instances before any handler runs, so a resolution
        failure (a subscriber class with no registered instance) propagates
        immediately and never causes partial delivery.

        Args:
            notification: The notification instance to publish

        Returns:
            NotificationHandler instances in registration order, empty if none subscribed

        Raises:
            ServiceNotFoundError: If a subscribed handler class has no
                registered instance in the service provider
        """
        handler_classes = registry.get_notification_handler_classes(type(notification))
        return [self._services.get(handler_class) for handler_class in handler_classes]

    def _resolve_behaviors(self, request: "Request[Any]") -> list[Any]:
        """Resolve applicable behavior instances for a request, in pipeline order.

        Walks the mediator's validated ``behaviors`` sequence, keeps the classes
        whose ``should_apply()`` accepts the request, and resolves each through
        the service provider - so instance lifetimes follow the provider's policy
        on every dispatch.

        Args:
            request: The request instance to process

        Returns:
            List of applicable behavior instances, first entry outermost
        """
        return [
            self._services.get(behavior_class)
            for behavior_class in self._behaviors
            if behavior_class.should_apply(request)
        ]
