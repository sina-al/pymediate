"""Bridge the composed Dependency Injector application into PyMediate."""

from dependency_injector import containers
from pymediate import Mediator
from pymediate.providers import DependencyInjectorServiceProvider

from shop.application.behaviours.logger import LoggerBehavior
from shop.application.behaviours.metrics import MetricsBehavior
from shop.application.behaviours.tracing import TracingBehavior


def create_mediator(container: containers.Container) -> Mediator:
    """Create a mediator over the application's complete nested container graph."""
    container.check_dependencies()
    services = DependencyInjectorServiceProvider(container)
    return Mediator(
        services,
        behaviors=[LoggerBehavior, TracingBehavior, MetricsBehavior],
    )
