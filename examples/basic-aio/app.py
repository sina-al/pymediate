"""The async mirror of basic-sync: the same task board on PyMediate's asynchronous API.

Demonstrates ``pymediate.aio``: handlers declare ``async def __call__``, dispatch is
awaited (``await mediator.send(...)``) and returns the typed response, and an async
``PipelineBehavior`` wraps dispatch selectively — its type parameter decides which
requests it applies to. ``Request`` and ``Services`` come from the sync package: only
``Handler``, ``Mediator``, and ``PipelineBehavior`` have aio variants.
"""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from pymediate import Request, Services
from pymediate.aio import Handler, Mediator, PipelineBehavior


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


# ---- Requests: each declares the response type it resolves to ----


@dataclass
class BoardMutation(Request[Task]):
    """Base for requests that change the board; the audit behavior applies to these."""


@dataclass
class AddTask(BoardMutation):
    """Add a task with the given title; responds with the created Task."""

    title: str


@dataclass
class CompleteTask(BoardMutation):
    """Mark a task as done; responds with the updated Task."""

    task_id: int


@dataclass
class ListOpenTasks(Request[list[Task]]):
    """List all tasks not yet done, oldest first."""


# ---- Handlers: exactly one per request type, all coroutines ----


class AddTaskHandler(Handler[AddTask]):
    """Creates tasks in the store."""

    def __init__(self, store: TaskStore) -> None:
        self._store = store

    async def __call__(self, request: AddTask) -> Task:
        await asyncio.sleep(0)  # stand-in for awaiting a real datastore
        task = Task(task_id=self._store.next_id, title=request.title)
        self._store.tasks[task.task_id] = task
        self._store.next_id += 1
        return task


class CompleteTaskHandler(Handler[CompleteTask]):
    """Marks existing tasks as done."""

    def __init__(self, store: TaskStore) -> None:
        self._store = store

    async def __call__(self, request: CompleteTask) -> Task:
        await asyncio.sleep(0)
        task = self._store.tasks.get(request.task_id)
        if task is None:
            raise TaskNotFoundError(f"No task with id {request.task_id}")
        task.done = True
        return task


class ListOpenTasksHandler(Handler[ListOpenTasks]):
    """Lists tasks that are still open."""

    def __init__(self, store: TaskStore) -> None:
        self._store = store

    async def __call__(self, request: ListOpenTasks) -> list[Task]:
        await asyncio.sleep(0)
        return [task for task in self._store.tasks.values() if not task.done]


# ---- Pipeline behavior: middleware around dispatch, selected by type parameter ----


class AuditTrail(PipelineBehavior[BoardMutation]):
    """Records every successful board mutation.

    The ``BoardMutation`` type parameter makes this behavior selective: the mediator
    runs it around ``AddTask`` and ``CompleteTask`` (subclasses of ``BoardMutation``)
    but not around the read-only ``ListOpenTasks``.
    """

    def __init__(self, log: list[str]) -> None:
        self._log = log

    async def __call__(
        self,
        request: BoardMutation,
        next: Callable[[], Awaitable[Task]],
    ) -> Task:
        task = await next()
        self._log.append(f"{type(request).__name__}: task {task.task_id}")
        return task


def build_mediator(store: TaskStore | None = None, audit_log: list[str] | None = None) -> Mediator:
    """Wire a mediator: one handler instance per request type, plus the audit behavior."""
    store = store if store is not None else TaskStore()
    audit_log = audit_log if audit_log is not None else []
    services = Services()
    services.add(AuditTrail(audit_log))
    services.add(AddTaskHandler(store))
    services.add(CompleteTaskHandler(store))
    services.add(ListOpenTasksHandler(store))
    return Mediator(services.provider())


async def main() -> None:
    """Run a short demo of the async task board."""
    audit_log: list[str] = []
    mediator = build_mediator(audit_log=audit_log)

    groceries = await mediator.send(AddTask(title="Buy groceries"))
    await mediator.send(AddTask(title="Write the release notes"))
    print(f"Created: {groceries}")

    await mediator.send(CompleteTask(task_id=groceries.task_id))

    for task in await mediator.send(ListOpenTasks()):
        print(f"Open: {task.title}")

    for entry in audit_log:
        print(f"Audited: {entry}")


if __name__ == "__main__":
    asyncio.run(main())
