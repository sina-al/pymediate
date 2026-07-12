"""A task board that emits events, built on PyMediate's async (top-level) API.

Demonstrates the *other* half of the mediator: ``publish``. Where ``send`` routes one
request to exactly one handler and awaits its typed response, ``publish`` fans one event
out to every handler subscribed to its type — none, one, or many — and awaits them all.
Here, completing a task publishes a ``TaskCompleted`` event that three independent handlers
react to concurrently: an audit log, a notifier, and a metrics counter. Everything imports
from ``pymediate`` directly; the sync mirror of this example is events-sync.
"""

import asyncio
from dataclasses import dataclass, field

from pymediate import Event, EventHandler, Mediator, Request, RequestHandler, Services


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


# ---- Event: broadcast to every subscriber, carries no response ----


@dataclass
class TaskCompleted(Event):
    """Announces that a task was completed; delivered to all its subscribers."""

    task_id: int
    title: str


# ---- Request handlers: exactly one per request type, all coroutines ----


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


# ---- Event handlers: any number may subscribe to one event ----


class AuditLog(EventHandler[TaskCompleted]):
    """Records every completion in an append-only audit trail."""

    def __init__(self, entries: list[str]) -> None:
        self._entries = entries

    async def __call__(self, event: TaskCompleted) -> None:
        await asyncio.sleep(0)
        self._entries.append(f"task {event.task_id} completed: {event.title}")


class Notifier(EventHandler[TaskCompleted]):
    """Queues a user-facing notification for each completion."""

    def __init__(self, outbox: list[str]) -> None:
        self._outbox = outbox

    async def __call__(self, event: TaskCompleted) -> None:
        await asyncio.sleep(0)
        self._outbox.append(f"Nice work! '{event.title}' is done.")


class Metrics(EventHandler[TaskCompleted]):
    """Counts completions for a dashboard."""

    def __init__(self, counts: dict[str, int]) -> None:
        self._counts = counts

    async def __call__(self, event: TaskCompleted) -> None:
        await asyncio.sleep(0)
        self._counts["completed"] = self._counts.get("completed", 0) + 1


def build_mediator(
    store: TaskStore | None = None,
    audit: list[str] | None = None,
    outbox: list[str] | None = None,
    counts: dict[str, int] | None = None,
) -> Mediator:
    """Wire a mediator: one handler per request, three subscribers for the event."""
    store = store if store is not None else TaskStore()
    audit = audit if audit is not None else []
    outbox = outbox if outbox is not None else []
    counts = counts if counts is not None else {}

    services = Services()
    services.add(AddTaskHandler(store))
    services.add(CompleteTaskHandler(store))
    # Each subscriber owns its own sink, so the concurrent fan-out stays independent.
    services.add(AuditLog(audit))
    services.add(Notifier(outbox))
    services.add(Metrics(counts))
    return Mediator(services.provider())


async def main() -> None:
    """Complete a task and watch one event fan out to three handlers."""
    store = TaskStore()
    audit: list[str] = []
    outbox: list[str] = []
    counts: dict[str, int] = {}
    mediator = build_mediator(store, audit, outbox, counts)

    task = await mediator.send(AddTask(title="Buy groceries"))
    await mediator.send(CompleteTask(task_id=task.task_id))

    # One publish, three independent reactions — the handlers run concurrently.
    await mediator.publish(TaskCompleted(task_id=task.task_id, title=task.title))

    print(f"Completed: {task.title}")
    print(f"Audit log: {audit}")
    print(f"Notifications: {outbox}")
    print(f"Metrics: {counts}")


if __name__ == "__main__":
    asyncio.run(main())
