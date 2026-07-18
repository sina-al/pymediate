"""Rate limiting applied to one handler with a method decorator."""

import functools
from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from pymediate.sync import Request, RequestHandler

from .domain import Task, TaskStore
from .limiter import RateLimiter


@dataclass
class AddTask(Request[Task]):
    """Add a task and return it."""

    title: str


def rate_limited[**P, T](func: Callable[P, T]) -> Callable[P, T]:
    """Check the limiter injected into the handler before calling the method."""

    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        handler = cast("AddTaskHandler", args[0])
        handler.limiter.check("AddTask")
        return func(*args, **kwargs)

    return wrapper


class AddTaskHandler(RequestHandler[AddTask]):
    """Add tasks, with rate limiting attached directly to ``__call__``."""

    def __init__(self, store: TaskStore, limiter: RateLimiter) -> None:
        self._store = store
        self._limiter = limiter

    @property
    def limiter(self) -> RateLimiter:
        """Return the limiter used by the decorator."""
        return self._limiter

    @rate_limited
    def __call__(self, request: AddTask) -> Task:
        task = Task(task_id=self._store.next_id, title=request.title)
        self._store.tasks[task.task_id] = task
        self._store.next_id += 1
        return task
