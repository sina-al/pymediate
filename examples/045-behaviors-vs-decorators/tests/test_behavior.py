"""Tests for the pipeline-behavior version."""

import pytest

from taskboard.behavior import AddTask, AddTaskHandler, build_mediator
from taskboard.domain import TaskStore
from taskboard.limiter import AlwaysAllow, CallCountLimiter, RateLimitExceededError


async def test_behavior_checks_its_configured_limiter_during_dispatch() -> None:
    mediator = build_mediator(limiter=CallCountLimiter(limit=2))

    await mediator.send(AddTask(title="one"))
    await mediator.send(AddTask(title="two"))
    with pytest.raises(RateLimitExceededError):
        await mediator.send(AddTask(title="three"))


async def test_behavior_dependency_is_swapped_when_the_mediator_is_built() -> None:
    mediator = build_mediator(limiter=AlwaysAllow())

    for i in range(5):
        await mediator.send(AddTask(title=f"bulk-{i}"))


async def test_mediators_have_independent_behavior_instances() -> None:
    strict = build_mediator(limiter=CallCountLimiter(limit=1))
    permissive = build_mediator(limiter=AlwaysAllow())

    await strict.send(AddTask(title="only one"))
    with pytest.raises(RateLimitExceededError):
        await strict.send(AddTask(title="too many"))

    await permissive.send(AddTask(title="fine"))
    await permissive.send(AddTask(title="also fine"))


async def test_direct_handler_call_bypasses_the_behavior() -> None:
    handler = AddTaskHandler(TaskStore())

    for i in range(3):
        await handler(AddTask(title=f"direct-{i}"))
