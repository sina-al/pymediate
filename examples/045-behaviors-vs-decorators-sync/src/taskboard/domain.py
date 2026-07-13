"""The task board's plain domain model — no cross-cutting concerns, no pymediate types.

Both `decorator.py` and `behavior.py` build their own request and handler on top of this
same `Task`/`TaskStore` pair, so the two approaches wrap the identical operation.
"""

from dataclasses import dataclass, field


@dataclass
class Task:
    """A task on the board."""

    task_id: int
    title: str


@dataclass
class TaskStore:
    """In-memory storage shared by both the decorator and the behavior handler."""

    tasks: dict[int, Task] = field(default_factory=dict)
    next_id: int = 1
