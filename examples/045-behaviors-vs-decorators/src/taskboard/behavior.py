"""The behavior approach — the same rate limit, injected instead of imported.

`RateLimitBehavior` receives its `RateLimiter` through the constructor, same as any other
collaborator. Swapping it for a test, or for a bulk-import tool that shouldn't be
throttled, is just constructing the behavior with a different argument — no module state,
no private attribute reached into, nothing to remember to put back afterward.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pymediate import Mediator, PipelineBehavior, Request, RequestHandler, Services

from .domain import Task, TaskStore
from .limiter import FixedWindowLimiter, RateLimiter


@dataclass
class AddTask(Request[Task]):
    """Add a task with the given title; responds with the created Task."""

    title: str


class AddTaskHandler(RequestHandler[AddTask]):
    """Plain — no rate limiting here. The limiter lives entirely in the behavior below."""

    def __init__(self, store: TaskStore) -> None:
        self._store = store

    async def __call__(self, request: AddTask) -> Task:
        task = Task(task_id=self._store.next_id, title=request.title)
        self._store.tasks[task.task_id] = task
        self._store.next_id += 1
        return task


class RateLimitBehavior(PipelineBehavior[Request]):
    """Check the injected limiter before letting a request reach its handler."""

    def __init__(self, limiter: RateLimiter) -> None:
        self._limiter = limiter

    async def __call__(self, request: Request[Any], next: Callable[[], Awaitable[Any]]) -> Any:
        self._limiter.check(type(request).__name__)
        return await next()


def build_mediator(
    *, store: TaskStore | None = None, limiter: RateLimiter | None = None
) -> Mediator:
    """Wire a mediator with the rate-limit behavior and the plain handler.

    Args:
        store: Task storage; a fresh empty store when omitted.
        limiter: The rate limiter the behavior checks against; a `FixedWindowLimiter` with
            a quota of 2 when omitted. Pass `AlwaysAllow()`, or any other `RateLimiter`, to
            swap it — no other change required.

    Returns:
        A mediator wired with `RateLimitBehavior` and `AddTaskHandler`.
    """
    store = store if store is not None else TaskStore()
    limiter = limiter if limiter is not None else FixedWindowLimiter(limit=2)

    services = Services()
    services.add(RateLimitBehavior(limiter))
    services.add(AddTaskHandler(store))
    return Mediator(services.provider())
