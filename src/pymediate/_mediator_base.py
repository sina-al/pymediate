"""Base mixin for mediator implementations (sync and async)."""

from pymediate.resolvers import Resolver


class MediatorBaseMixin:
    """Mixin providing shared logic for both sync and async mediators.

    This mixin contains the common initialization and resolver storage logic
    that is shared between the synchronous Mediator and asynchronous Mediator.

    The actual send() method is implemented differently in each variant:
    - Synchronous: def send(...) -> ResponseT
    - Asynchronous: async def send(...) -> ResponseT

    Attributes:
        _resolver: The resolver instance used to obtain handler instances.
    """

    _resolver: Resolver

    def __init__(self, resolver: Resolver) -> None:
        """Initialize mediator with a resolver for obtaining handler instances.

        Args:
            resolver: Any object implementing the Resolver protocol. This can be
                a SimpleResolver, DependencyInjectorResolver, or your own custom
                resolver implementation.

        Examples:
            ```python
            resolver = SimpleResolver()
            mediator = Mediator(resolver)
            ```
        """
        self._resolver = resolver
