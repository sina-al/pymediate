"""The task board's data and store — the responses the messages resolve to.

Nothing here is about message *design*; that's `messages.py`. These are the plain result
types and the in-memory store the handlers read and write.
"""

from dataclasses import dataclass, field


@dataclass
class Task:
    """A task on the board."""

    task_id: int
    title: str
    tags: tuple[str, ...]
    priority: int


@dataclass
class Webhook:
    """A registered webhook — the result of accepting a RegisterWebhook request."""

    webhook_id: int
    url: str


@dataclass
class TaskStore:
    """In-memory task storage (a stand-in for a database)."""

    tasks: dict[int, Task] = field(default_factory=dict)
    next_id: int = 1

    def add(self, title: str, tags: tuple[str, ...], priority: int) -> Task:
        """Persist a new task and return it."""
        task = Task(task_id=self.next_id, title=title, tags=tags, priority=priority)
        self.tasks[task.task_id] = task
        self.next_id += 1
        return task

    def with_tag(self, tag: str) -> list[Task]:
        """Return every task carrying the given tag."""
        return [task for task in self.tasks.values() if tag in task.tags]
