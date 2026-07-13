"""The whole ``send()`` loop in one file, on PyMediate's synchronous API (``pymediate.sync``).

You have a request. You want a typed response back. This is the entire round trip without
an event loop: declare a request typed by its response (``Request[Task]``), write one
handler, register it in ``Services``, then call ``mediator.send(...)``. The response type
you name once on the request flows all the way to the call site — no casts. The async
mirror of this example is 010-basic, built on the top-level ``pymediate`` API.
"""

from dataclasses import dataclass, field

from pymediate.sync import Mediator, Request, RequestHandler, Services


@dataclass
class Task:
    """A task on the board, as stored and handed back to the caller."""

    task_id: int
    title: str
    done: bool = False


@dataclass
class TaskStore:
    """In-memory storage (a stand-in for a real repository)."""

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

    def __call__(self, request: AddTask) -> Task:
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


def main() -> None:
    """Send one request and get its typed response back."""
    mediator = build_mediator()

    task = mediator.send(AddTask(title="Buy groceries"))
    # `task` is inferred as Task — the same zero-cast round trip as 010-basic, minus the
    # await. `reveal_type(task)` reports "Task", and task.task_id is a known int.
    assert isinstance(task, Task)
    print(f"Created: {task}")
    print(f"Assigned id: {task.task_id}")


if __name__ == "__main__":
    main()
