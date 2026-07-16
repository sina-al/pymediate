"""Wiring: the one place that builds a mediator from the domain, messages, and handlers.

Every adapter in ``adapters/`` calls exactly this and nothing else to get a working
application — that's what makes each adapter a thin doorway rather than its own
copy of the wiring.
"""

from pymediate.sync import Mediator, Services

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
