"""Wiring: the one place that builds a mediator from the domain, messages, and handlers.

Every adapter in ``adapters/`` calls this function to get the configured application. The
adapters translate input and output without copying the wiring.
"""

from pymediate import Mediator, Services

from .domain import TaskStore
from .handlers import AddTaskHandler, CompleteTaskHandler, ListOpenTasksHandler


def build_mediator(store: TaskStore | None = None) -> Mediator:
    """Wire a mediator: register one handler instance per request type."""
    store = store if store is not None else TaskStore()
    services = Services()
    services.add(AddTaskHandler(store))
    services.add(CompleteTaskHandler(store))
    services.add(ListOpenTasksHandler(store))
    return Mediator(services.provider())
