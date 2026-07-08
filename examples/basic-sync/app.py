"""A tiny task board built on PyMediate's synchronous API.

Demonstrates the core loop: define requests typed by their response
(``Request[Response]``), write one handler per request, register the handlers in
``Services``, and send requests through a ``Mediator`` — which infers the response type
from the request, end to end.
"""

from dataclasses import dataclass, field

from pymediate import Handler, Mediator, Request, Services


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


# ---- Requests: each declares the response type it resolves to ----


@dataclass
class AddTask(Request[Task]):
    """Add a task with the given title; responds with the created Task."""

    title: str


@dataclass
class CompleteTask(Request[Task]):
    """Mark a task as done; responds with the updated Task."""

    task_id: int


@dataclass
class ListOpenTasks(Request[list[Task]]):
    """List all tasks not yet done, oldest first."""


# ---- Handlers: exactly one per request type ----


class AddTaskHandler(Handler[AddTask]):
    """Creates tasks in the store."""

    def __init__(self, store: TaskStore) -> None:
        self._store = store

    def __call__(self, request: AddTask) -> Task:
        task = Task(task_id=self._store.next_id, title=request.title)
        self._store.tasks[task.task_id] = task
        self._store.next_id += 1
        return task


class CompleteTaskHandler(Handler[CompleteTask]):
    """Marks existing tasks as done."""

    def __init__(self, store: TaskStore) -> None:
        self._store = store

    def __call__(self, request: CompleteTask) -> Task:
        task = self._store.tasks.get(request.task_id)
        if task is None:
            raise TaskNotFoundError(f"No task with id {request.task_id}")
        task.done = True
        return task


class ListOpenTasksHandler(Handler[ListOpenTasks]):
    """Lists tasks that are still open."""

    def __init__(self, store: TaskStore) -> None:
        self._store = store

    def __call__(self, request: ListOpenTasks) -> list[Task]:
        return [task for task in self._store.tasks.values() if not task.done]


def build_mediator(store: TaskStore | None = None) -> Mediator:
    """Wire a mediator: register one handler instance per request type."""
    store = store if store is not None else TaskStore()
    services = Services()
    services.add(AddTaskHandler(store))
    services.add(CompleteTaskHandler(store))
    services.add(ListOpenTasksHandler(store))
    return Mediator(services.provider())


def main() -> None:
    """Run a short demo of the task board."""
    mediator = build_mediator()

    groceries = mediator.send(AddTask(title="Buy groceries"))
    mediator.send(AddTask(title="Write the release notes"))
    print(f"Created: {groceries}")

    mediator.send(CompleteTask(task_id=groceries.task_id))

    for task in mediator.send(ListOpenTasks()):
        print(f"Open: {task.title}")


if __name__ == "__main__":
    main()
