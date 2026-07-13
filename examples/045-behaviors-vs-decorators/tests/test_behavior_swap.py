"""The behavior version's tests — swapping the limiter is a constructor argument."""

import pytest

from taskboard.behavior import AddTask, build_mediator
from taskboard.limiter import AlwaysAllow, FixedWindowLimiter, RateLimitExceededError


async def test_default_limiter_enforces_its_quota() -> None:
    mediator = build_mediator()  # FixedWindowLimiter(limit=2) by default

    await mediator.send(AddTask(title="one"))
    await mediator.send(AddTask(title="two"))
    with pytest.raises(RateLimitExceededError):
        await mediator.send(AddTask(title="three"))


async def test_swapping_the_limiter_is_a_constructor_argument() -> None:
    """No module state, no monkeypatching — a different mediator, a different limiter."""
    mediator = build_mediator(limiter=AlwaysAllow())

    for i in range(5):  # would exceed FixedWindowLimiter(limit=2); AlwaysAllow never raises
        await mediator.send(AddTask(title=f"bulk-{i}"))


async def test_two_mediators_keep_independent_limiters() -> None:
    """Unlike the decorator version, nothing is shared unless you choose to share it."""
    strict = build_mediator(limiter=FixedWindowLimiter(limit=1))
    lenient = build_mediator(limiter=AlwaysAllow())

    await strict.send(AddTask(title="only one"))
    with pytest.raises(RateLimitExceededError):
        await strict.send(AddTask(title="too many"))

    # `lenient` never shared `strict`'s limiter — it has its own.
    await lenient.send(AddTask(title="fine"))
    await lenient.send(AddTask(title="also fine"))
