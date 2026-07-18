"""The task requests, handlers, and dependencies wrapped by the behaviors.

Two request *families* carry the routing that the pipeline keys on:

- ``Command`` — requests that change the board (authorized, transactional).
- ``Query`` — read-only requests (cacheable).

A behavior selects a family by naming it as its type parameter. ``TaskStore``,
``FakeCache``, and ``Principal`` keep the example in memory. Production implementations
need their own persistence, cache-key, serialization, expiry, invalidation, and identity
rules.
"""

import asyncio
from dataclasses import dataclass, field
from typing import Any

from pymediate import Request, RequestHandler


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
    reads: int = 0  # counts handler-served reads, so tests can prove a cache hit skipped one


class FakeCache:
    """An in-process dictionary used to demonstrate a cached response.

    A production cache also needs stable keys, serialization, expiry, and invalidation.
    """

    def __init__(self) -> None:
        self._store: dict[str, Any] = {}

    def get(self, key: str) -> Any:
        """Return the cached value for ``key``, or ``None`` when nothing is stored."""
        return self._store.get(key)

    def set(self, key: str, value: Any) -> None:
        """Store ``value`` under ``key``."""
        self._store[key] = value


@dataclass
class Principal:
    """The user a request runs as — a stand-in for an authenticated identity."""

    name: str
    can_write: bool


class TaskNotFoundError(Exception):
    """Raised when a request references a task id that doesn't exist."""


class AccessDeniedError(Exception):
    """Raised when a principal lacks permission to run a command."""


# ---- Request families: the marker types the behaviors route on ----
#
# A behavior selects requests by naming a type as its parameter, so these two families
# are what make the pipeline selective. Both subclass ``Request`` (that's what lets a
# behavior target them), but they bind no concrete response type — each concrete request
# below does that itself by *also* inheriting ``Request[SomeResponse]`` directly, which is
# how PyMediate infers what ``send`` returns.


class Command(Request[Any]):
    """Marker base for requests that change the board — authorized and transactional."""


@dataclass
class Query(Request[Any]):
    """Marker base for read-only requests — cacheable unless a caller opts out per request."""

    cacheable: bool = field(default=True, kw_only=True)


# ---- Concrete requests: each declares the response type it resolves to ----


@dataclass
class AddTask(Command, Request[Task]):
    """Add a task with the given title; responds with the created Task."""

    title: str


@dataclass
class CompleteTask(Command, Request[Task]):
    """Mark a task as done; responds with the updated Task."""

    task_id: int


@dataclass
class GetTask(Query, Request[Task]):
    """Fetch a single task by id; responds with the Task."""

    task_id: int


@dataclass
class ListOpenTasks(Query, Request[list[Task]]):
    """List all tasks not yet done. Defaults uncacheable — the list changes often."""

    cacheable: bool = field(default=False, kw_only=True)


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


class GetTaskHandler(RequestHandler[GetTask]):
    """Reads a single task, counting each real read so cache hits are observable."""

    def __init__(self, store: TaskStore) -> None:
        self._store = store

    async def __call__(self, request: GetTask) -> Task:
        await asyncio.sleep(0)
        task = self._store.tasks.get(request.task_id)
        if task is None:
            raise TaskNotFoundError(f"No task with id {request.task_id}")
        self._store.reads += 1
        return task


class ListOpenTasksHandler(RequestHandler[ListOpenTasks]):
    """Lists tasks that are still open."""

    def __init__(self, store: TaskStore) -> None:
        self._store = store

    async def __call__(self, request: ListOpenTasks) -> list[Task]:
        await asyncio.sleep(0)
        return [task for task in self._store.tasks.values() if not task.done]
