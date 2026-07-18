"""The domain: a task, its store, and the one error it can raise.

Nothing here imports a request, handler, or mediator; those are defined in ``messages.py`` and
``handlers.py``. This module contains the record serialized by adapters and the store mutated
by handlers.
"""

from dataclasses import dataclass, field


@dataclass
class Task:
    """A task on the board."""

    task_id: int
    title: str
    done: bool = False


@dataclass
class TaskStore:
    """In-memory storage shared by the handlers (a stand-in for a real async repository)."""

    tasks: dict[int, Task] = field(default_factory=dict)
    next_id: int = 1


class TaskNotFoundError(Exception):
    """Raised when a request references a task id that doesn't exist."""
