"""The domain: a task, its store, and the one error it can raise.

Nothing here knows about a request, a handler, or a mediator — those live in
``messages.py`` and ``handlers.py``. This module is deliberately the smallest possible
slice: the record an adapter eventually serializes, and the store a handler mutates.
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
    """In-memory storage shared by the handlers (a stand-in for a real repository)."""

    tasks: dict[int, Task] = field(default_factory=dict)
    next_id: int = 1


class TaskNotFoundError(Exception):
    """Raised when a request references a task id that doesn't exist."""
