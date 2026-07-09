"""Base mixin for mediator implementations (sync and async)."""

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from .. import errors
from . import registry

if TYPE_CHECKING:
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
    """

    _services: "ServiceProvider"

    def __init__(self, services: "ServiceProvider") -> None:
        """Initialize mediator with services for obtaining handler and behavior instances.

        Args:
            services: Any object implementing the ServiceProvider protocol.
                This can be a ServiceProvider from Services.provider(),
                a DependencyInjectorServiceProvider, or your own custom implementation.

        Examples:
            ```python
            from pymediate import Mediator
            from pymediate.service import Services

            services = Services()
            services.add(CreateUserHandler())
            provider = services.provider()

            mediator = Mediator(provider)
            ```

            With dependency injection:
            ```python
            from pymediate.providers import DependencyInjectorServiceProvider

            container = AppContainer()
            provider = DependencyInjectorServiceProvider(container)
            mediator = Mediator(provider)
            ```
        """
        self._services = services

    def _resolve_handler(self, request: "Request[Any]") -> Any:
        """Resolve the handler for a request.

        Args:
            request: The request instance to process

        Returns:
            Handler instance for the request

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

    def _resolve_behaviors(
        self, request: "Request[Any]", pipeline_behavior_type: type
    ) -> list[Any]:
        """Resolve applicable behaviors for a request.

        Args:
            request: The request instance to process
            pipeline_behavior_type: The PipelineBehavior type (sync or async variant)

        Returns:
            List of applicable behavior instances
        """
        # Get all registered pipeline behaviors
        all_behaviors: Sequence[Any] = self._services.get_all(pipeline_behavior_type)

        # Filter behaviors to only those that apply to this request
        return [behavior for behavior in all_behaviors if type(behavior).should_apply(request)]
