"""Run both versions back to back — the decorator hits a wall, the behavior doesn't.

`uv run taskboard` runs this. Read it top to bottom: the decorator version's quota can't
be raised without reaching into module state (that friction is proven in
`tests/test_decorator_friction.py`); the behavior version's quota is just a constructor
argument, swapped between two mediators with nothing else different.
"""

import asyncio

from taskboard import behavior, decorator
from taskboard.domain import TaskStore
from taskboard.limiter import AlwaysAllow, FixedWindowLimiter, RateLimitExceededError


async def main() -> None:
    """Run the decorator version to its limit, then the behavior version, twice."""
    print("== decorator version: quota bound at import time ==")
    handler = decorator.AddTaskHandler(TaskStore())
    await handler(decorator.AddTask(title="write the report"))
    await handler(decorator.AddTask(title="review the report"))
    try:
        await handler(decorator.AddTask(title="one more"))
    except RateLimitExceededError as exc:
        print(f"blocked: {exc}")
    print("(no constructor argument raises this quota — only patching decorator._limiter)")

    print()
    print("== behavior version: same quota, passed in ==")
    mediator = behavior.build_mediator(limiter=FixedWindowLimiter(limit=2))
    await mediator.send(behavior.AddTask(title="write the report"))
    await mediator.send(behavior.AddTask(title="review the report"))
    try:
        await mediator.send(behavior.AddTask(title="one more"))
    except RateLimitExceededError as exc:
        print(f"blocked: {exc}")

    print()
    print("== behavior version, swapped for a bulk import — nothing else changes ==")
    bulk_mediator = behavior.build_mediator(limiter=AlwaysAllow())
    for i in range(5):
        await bulk_mediator.send(behavior.AddTask(title=f"bulk-{i}"))
    print("added 5 tasks: a different limiter argument, same handler, same behavior class")


def run() -> None:
    """Console-script entry point (`uv run taskboard`)."""
    asyncio.run(main())


if __name__ == "__main__":
    run()
