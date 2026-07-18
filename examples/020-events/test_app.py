"""Tests for the events example — the examples contract's `uv run pytest` entrypoint."""

import pytest
from pymediate import Mediator

from app import Dashboard, TaskArchived, TaskCompleted, build_mediator


@pytest.fixture
def dashboard() -> Dashboard:
    return Dashboard()


@pytest.fixture
def mediator(dashboard: Dashboard) -> Mediator:
    return build_mediator(dashboard)


async def test_publish_runs_all_three_handlers(mediator: Mediator, dashboard: Dashboard) -> None:
    await mediator.publish(TaskCompleted(task_id=1, title="Ship it"))

    # notify + stats + audit each contribute a started and a done line.
    done = [line for line in dashboard.feed if "done" in line]
    assert len(done) == 3
    assert dashboard.completed == 1
    assert any("Ship it" in line for line in done)
    assert any("task 1 logged" in line for line in done)


async def test_delivery_is_concurrent(mediator: Mediator, dashboard: Dashboard) -> None:
    await mediator.publish(TaskCompleted(task_id=1, title="Ship it"))

    # Every subscriber starts before any finishes — only possible if the mediator ran
    # them together. Sequential delivery would pair each started with its own done.
    last_start = max(i for i, line in enumerate(dashboard.feed) if "started" in line)
    first_done = min(i for i, line in enumerate(dashboard.feed) if "done" in line)
    assert last_start < first_done


async def test_zero_subscribers_is_a_noop(mediator: Mediator, dashboard: Dashboard) -> None:
    # Nothing subscribes to TaskArchived; publishing it must succeed and do nothing.
    await mediator.publish(TaskArchived(task_id=1))

    assert dashboard.feed == []
    assert dashboard.completed == 0


async def test_dispatch_is_by_exact_type(mediator: Mediator, dashboard: Dashboard) -> None:
    # TaskArchived subscribers don't exist, and TaskCompleted subscribers ignore it —
    # events dispatch on the exact published class, never a sibling type.
    await mediator.publish(TaskArchived(task_id=1))
    await mediator.publish(TaskCompleted(task_id=1, title="Ship it"))

    assert dashboard.completed == 1


async def test_each_publish_reacts_again(mediator: Mediator, dashboard: Dashboard) -> None:
    await mediator.publish(TaskCompleted(task_id=1, title="first"))
    await mediator.publish(TaskCompleted(task_id=2, title="second"))

    assert dashboard.completed == 2


async def test_feed_records_started_before_done_per_subscriber(
    mediator: Mediator, dashboard: Dashboard
) -> None:
    await mediator.publish(TaskCompleted(task_id=7, title="Write the release notes"))

    for name in ("notify", "stats", "audit"):
        marks = [line for line in dashboard.feed if line.startswith(name)]
        assert [mark.split()[1] for mark in marks] == ["started", "done"]
