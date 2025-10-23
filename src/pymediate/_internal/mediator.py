"""Base mixin for mediator implementations (sync and async)."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..service import ServiceProvider


class MediatorMixin:
    """Mixin providing shared logic for both sync and async mediators.

    This mixin contains the common initialization and service provider storage logic
    that is shared between the synchronous Mediator and asynchronous Mediator.

    The actual send() method is implemented differently in each variant:
    - Synchronous: def send(...) -> ResponseT
    - Asynchronous: async def send(...) -> ResponseT

    Attributes:
        _service_provider: The service provider instance used to obtain handler instances.
    """

    _service_provider: "ServiceProvider"

    def __init__(self, service_provider: "ServiceProvider") -> None:
        """Initialize mediator with a service provider for obtaining handler instances.

        Args:
            service_provider: Any object implementing the ServiceProvider protocol.
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
        self._service_provider = service_provider
