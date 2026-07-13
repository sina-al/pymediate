"""The decorator version's tests — and the seam it doesn't have.

`AddTaskHandler.__call__` is rate-limited by `@rate_limited`, which checks the
*module-level* `taskboard.decorator._limiter` bound at import time. There is no
constructor parameter for it — the only way to use a different limiter is to reach into
the module and reassign its private global, then remember to put it back so the next test
doesn't inherit an already-used-up limiter.
"""

import pytest

from taskboard import decorator
from taskboard.domain import TaskStore
from taskboard.limiter import AlwaysAllow, FixedWindowLimiter, RateLimitExceededError


@pytest.fixture(autouse=True)
def _fresh_module_limiter() -> None:
    """Reset the module-level limiter before every test.

    Without this, `_limiter` stays shared — and once exhausted — across every test in this
    file, because it's one process-global instance bound at import time. The behavior
    version needs no equivalent fixture (see `test_behavior_swap.py`): each test just
    constructs its own mediator with its own limiter.
    """
    decorator._limiter = FixedWindowLimiter(limit=2)


def test_module_limiter_is_shared_and_eventually_exhausted() -> None:
    handler = decorator.AddTaskHandler(TaskStore())

    handler(decorator.AddTask(title="one"))
    handler(decorator.AddTask(title="two"))
    with pytest.raises(RateLimitExceededError):
        handler(decorator.AddTask(title="three"))  # the module limiter's quota is 2


def test_swapping_the_limiter_requires_reaching_past_the_class() -> None:
    """There's no constructor argument for this — only monkeypatching module state."""
    handler = decorator.AddTaskHandler(TaskStore())

    original = decorator._limiter  # the class gives you nothing to pass instead
    decorator._limiter = AlwaysAllow()
    try:
        for i in range(5):  # would exceed the real limiter's quota of 2
            handler(decorator.AddTask(title=f"bulk-{i}"))
    finally:
        decorator._limiter = original  # must restore it, or later tests inherit this one


def test_two_handler_instances_share_the_same_limiter() -> None:
    """Unlike the behavior version, there's no way to give two handlers independent quotas."""
    first = decorator.AddTaskHandler(TaskStore())
    second = decorator.AddTaskHandler(TaskStore())

    first(decorator.AddTask(title="one"))
    second(decorator.AddTask(title="two"))  # counts against the SAME module limiter
    with pytest.raises(RateLimitExceededError):
        first(decorator.AddTask(title="three"))
