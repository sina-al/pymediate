"""Rate limiting configured as a pipeline behavior for ``AddTask`` requests."""

from dataclasses import dataclass

from pymediate import Mediator, Next, PipelineBehavior, Request, RequestHandler, Services

from .domain import Task, TaskStore
from .limiter import CallCountLimiter, RateLimiter


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


class RateLimitBehavior(PipelineBehavior[AddTask]):
    """Check the configured limiter before an ``AddTask`` reaches its handler."""

    def __init__(self, limiter: RateLimiter) -> None:
        self._limiter = limiter

    async def __call__(self, request: AddTask, next: Next[Task]) -> Task:
        self._limiter.check(type(request).__name__)
        return await next()


def build_mediator(
    *, store: TaskStore | None = None, limiter: RateLimiter | None = None
) -> Mediator:
    """Wire a mediator with the rate-limit behavior and the plain handler.

    Args:
        store: Task storage; a fresh empty store when omitted.
        limiter: The rate limiter the behavior checks. Defaults to a
            `CallCountLimiter` with a quota of 2.

    Returns:
        A mediator wired with `RateLimitBehavior` and `AddTaskHandler`.
    """
    store = store if store is not None else TaskStore()
    limiter = limiter if limiter is not None else CallCountLimiter(limit=2)

    services = Services()
    services.add(RateLimitBehavior(limiter))
    services.add(AddTaskHandler(store))
    return Mediator(services.provider())
