"""Bridge the composed Dependency Injector application into PyMediate."""

from dependency_injector import containers
from pymediate import Mediator
from pymediate.providers import DependencyInjectorServiceProvider


def create_mediator(container: containers.Container) -> Mediator:
    """Create a mediator over the application's complete nested container graph."""
    container.check_dependencies()
    services = DependencyInjectorServiceProvider(container)
    return Mediator(services)
