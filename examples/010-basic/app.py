"""The whole ``send()`` loop in one file, on PyMediate's async (top-level) API.

Declare a request with its response type (``Request[Task]``), write a handler with a checked
return annotation, register it in ``Services``, then call ``await mediator.send(...)``.
The request base determines the call-site return type. The synchronous mirror is
010-basic-sync, built on ``pymediate.sync``.
"""

import asyncio
from dataclasses import dataclass, field

from pymediate import Mediator, Request, RequestHandler, Services


@dataclass
class Task:
    """A task on the board, as stored and handed back to the caller."""

    task_id: int
    title: str
    done: bool = False


@dataclass
class TaskStore:
    """In-memory storage (a stand-in for a real async repository)."""

    tasks: dict[int, Task] = field(default_factory=dict)
    next_id: int = 1


# ---- The request declares the response type it resolves to ----


@dataclass
class AddTask(Request[Task]):
    """Add a task with the given title; sending it responds with the created Task."""

    title: str


# ---- One handler resolves that request ----


class AddTaskHandler(RequestHandler[AddTask]):
    """Stores the task and returns it with its server-assigned id."""

    def __init__(self, store: TaskStore) -> None:
        self._store = store

    async def __call__(self, request: AddTask) -> Task:
        await asyncio.sleep(0)  # stand-in for awaiting a real datastore
        task = Task(task_id=self._store.next_id, title=request.title)
        self._store.tasks[task.task_id] = task
        self._store.next_id += 1
        return task


def build_mediator(store: TaskStore | None = None) -> Mediator:
    """Wire a mediator: register the one handler that resolves AddTask."""
    store = store if store is not None else TaskStore()
    services = Services()
    services.add(AddTaskHandler(store))
    return Mediator(services.provider())


async def main() -> None:
    """Send one request and get its typed response back."""
    mediator = build_mediator()

    task = await mediator.send(AddTask(title="Buy groceries"))
    # `task` is inferred as Task from AddTask(Request[Task]). The handler's separate
    # `-> Task` annotation checks its implementation.
    print(f"Created: {task}")
    print(f"Assigned id: {task.task_id}")


if __name__ == "__main__":
    asyncio.run(main())
