"""Tests for the pipeline-behavior version."""

import pytest

from taskboard.behavior import AddTask, AddTaskHandler, build_mediator
from taskboard.domain import TaskStore
from taskboard.limiter import AlwaysAllow, CallCountLimiter, RateLimitExceededError


def test_behavior_checks_its_configured_limiter_during_dispatch() -> None:
    mediator = build_mediator(limiter=CallCountLimiter(limit=2))

    mediator.send(AddTask(title="one"))
    mediator.send(AddTask(title="two"))
    with pytest.raises(RateLimitExceededError):
        mediator.send(AddTask(title="three"))


def test_behavior_dependency_is_swapped_when_the_mediator_is_built() -> None:
    mediator = build_mediator(limiter=AlwaysAllow())

    for i in range(5):
        mediator.send(AddTask(title=f"bulk-{i}"))


def test_mediators_have_independent_behavior_instances() -> None:
    strict = build_mediator(limiter=CallCountLimiter(limit=1))
    permissive = build_mediator(limiter=AlwaysAllow())

    strict.send(AddTask(title="only one"))
    with pytest.raises(RateLimitExceededError):
        strict.send(AddTask(title="too many"))

    permissive.send(AddTask(title="fine"))
    permissive.send(AddTask(title="also fine"))


def test_direct_handler_call_bypasses_the_behavior() -> None:
    handler = AddTaskHandler(TaskStore())

    for i in range(3):
        handler(AddTask(title=f"direct-{i}"))
