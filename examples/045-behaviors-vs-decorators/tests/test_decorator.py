"""Tests for the method-decorator version."""

import pytest

from taskboard.decorator import AddTask, AddTaskHandler
from taskboard.domain import TaskStore
from taskboard.limiter import AlwaysAllow, CallCountLimiter, RateLimitExceededError


async def test_decorator_checks_the_handler_limiter_on_a_direct_call() -> None:
    handler = AddTaskHandler(TaskStore(), CallCountLimiter(limit=2))

    await handler(AddTask(title="one"))
    await handler(AddTask(title="two"))
    with pytest.raises(RateLimitExceededError):
        await handler(AddTask(title="three"))


async def test_decorator_dependency_is_swapped_through_the_handler_constructor() -> None:
    handler = AddTaskHandler(TaskStore(), AlwaysAllow())

    for i in range(5):
        await handler(AddTask(title=f"bulk-{i}"))


async def test_decorated_handlers_have_independent_limiters() -> None:
    strict = AddTaskHandler(TaskStore(), CallCountLimiter(limit=1))
    permissive = AddTaskHandler(TaskStore(), AlwaysAllow())

    await strict(AddTask(title="only one"))
    with pytest.raises(RateLimitExceededError):
        await strict(AddTask(title="too many"))

    await permissive(AddTask(title="fine"))
    await permissive(AddTask(title="also fine"))
