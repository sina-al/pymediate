"""The application core: a task board that knows nothing about its adapters.

The async mirror of `examples/adapters-sync/`'s core — same requests, same wiring,
handlers declared ``async def`` on ``pymediate.aio``. Everything the three adapters
in this example deliver — FastAPI endpoints, aiohttp routes, an asyncclick CLI — is
implemented here against pymediate and the standard library alone. The adapters
(``fastapi_app.py``, ``aiohttp_app.py``, ``cli.py``) only translate their framework's
input into these request objects and ``await mediator.send()`` calls; swapping or
adding a framework never touches this file.
"""

import asyncio
from dataclasses import dataclass, field

from pymediate import Request, Services
from pymediate.aio import RequestHandler, Mediator


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


# ---- Handlers: exactly one per request type, all coroutines ----


class AddTaskHandler(RequestHandler[AddTask]):
    """Creates tasks in the store."""

    def __init__(self, store: TaskStore) -> None:
        self._store = store

    async def __call__(self, request: AddTask) -> Task:
        await asyncio.sleep(0)  # stand-in for awaiting a real datastore
        task = Task(task_id=self._store.next_id, title=request.title)
        self._store.tasks[task.task_id] = task
        self._store.next_id += 1
        return task


class CompleteTaskHandler(RequestHandler[CompleteTask]):
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


class ListOpenTasksHandler(RequestHandler[ListOpenTasks]):
    """Lists tasks that are still open."""

    def __init__(self, store: TaskStore) -> None:
        self._store = store

    async def __call__(self, request: ListOpenTasks) -> list[Task]:
        await asyncio.sleep(0)
        return [task for task in self._store.tasks.values() if not task.done]


def build_mediator(store: TaskStore | None = None) -> Mediator:
    """Wire a mediator: register one handler instance per request type."""
    store = store if store is not None else TaskStore()
    services = Services()
    services.add(AddTaskHandler(store))
    services.add(CompleteTaskHandler(store))
    services.add(ListOpenTasksHandler(store))
    return Mediator(services.provider())
