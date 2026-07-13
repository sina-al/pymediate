"""The decorator approach — and exactly where it runs out of road.

`rate_limited` is a plain function decorator wrapping `AddTaskHandler.__call__`. It needs a
`RateLimiter` to call through to, but a decorator applied at class-body evaluation time has
no parameter through which to *receive* one — its only option is to reach for something
already importable, which means a module-level instance bound once, at import time, and
shared by every call `AddTaskHandler` ever makes.

That's fine until you want a different limiter: a fake for a test, a generous one for a
bulk-import tool. There's no constructor argument for it — see
`tests/test_decorator_friction.py` for what swapping it actually takes.

This is the synchronous mirror of `examples/045-behaviors-vs-decorators/decorator.py` —
same structure, plain `def` instead of `async def`.
"""

import functools
from collections.abc import Callable
from dataclasses import dataclass

from pymediate.sync import Request, RequestHandler

from .domain import Task, TaskStore
from .limiter import FixedWindowLimiter, RateLimiter


@dataclass
class AddTask(Request[Task]):
    """Add a task with the given title; responds with the created Task."""

    title: str


# Bound once, at import time. Every call through @rate_limited shares this exact instance —
# there is no parameter through which a caller can hand it a different one.
_limiter: RateLimiter = FixedWindowLimiter(limit=2)


def rate_limited[**P, T](func: Callable[P, T]) -> Callable[P, T]:
    """Check the module-level `_limiter` before calling through to `func`."""

    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        _limiter.check("AddTask")
        return func(*args, **kwargs)

    return wrapper


class AddTaskHandler(RequestHandler[AddTask]):
    """Rate-limited via `@rate_limited` — bound to the module's `_limiter`, not injected."""

    def __init__(self, store: TaskStore) -> None:
        self._store = store

    @rate_limited
    def __call__(self, request: AddTask) -> Task:
        task = Task(task_id=self._store.next_id, title=request.title)
        self._store.tasks[task.task_id] = task
        self._store.next_id += 1
        return task
