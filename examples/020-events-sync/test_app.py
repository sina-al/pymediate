"""Tests for the notifications-sync example — the examples contract's `uv run pytest` entrypoint."""

import pytest
from pymediate.sync import Mediator

from app import Dashboard, TaskArchived, TaskCompleted, build_mediator


@pytest.fixture
def dashboard() -> Dashboard:
    return Dashboard()


@pytest.fixture
def mediator(dashboard: Dashboard) -> Mediator:
    return build_mediator(dashboard)


def test_publish_runs_all_three_handlers(mediator: Mediator, dashboard: Dashboard) -> None:
    mediator.publish(TaskCompleted(task_id=1, title="Ship it"))

    done = [line for line in dashboard.feed if "done" in line]
    assert len(done) == 3
    assert dashboard.completed == 1
    assert any("Ship it" in line for line in done)
    assert any("task 1 logged" in line for line in done)


def test_delivery_is_sequential(mediator: Mediator, dashboard: Dashboard) -> None:
    mediator.publish(TaskCompleted(task_id=1, title="Ship it"))

    # Sequential delivery: each subscriber's started is immediately followed by its done,
    # in registration order. Concurrent delivery would put all starteds first.
    assert dashboard.feed == [
        "notify  started",
        "notify  done    (queued task completion for Ship it)",
        "stats   started",
        "stats   done    (completions now 1)",
        "audit   started",
        "audit   done    (task 1 logged)",
    ]


def test_zero_subscribers_is_a_noop(mediator: Mediator, dashboard: Dashboard) -> None:
    # Nothing subscribes to TaskArchived; publishing it must succeed and do nothing.
    mediator.publish(TaskArchived(task_id=1))

    assert dashboard.feed == []
    assert dashboard.completed == 0


def test_dispatch_is_by_exact_type(mediator: Mediator, dashboard: Dashboard) -> None:
    # TaskArchived subscribers don't exist, and TaskCompleted subscribers ignore it —
    # notifications dispatch on the exact published class, never a sibling type.
    mediator.publish(TaskArchived(task_id=1))
    mediator.publish(TaskCompleted(task_id=1, title="Ship it"))

    assert dashboard.completed == 1


def test_each_publish_reacts_again(mediator: Mediator, dashboard: Dashboard) -> None:
    mediator.publish(TaskCompleted(task_id=1, title="first"))
    mediator.publish(TaskCompleted(task_id=2, title="second"))

    assert dashboard.completed == 2


def test_feed_records_started_before_done_per_subscriber(
    mediator: Mediator, dashboard: Dashboard
) -> None:
    mediator.publish(TaskCompleted(task_id=7, title="Write the release notes"))

    for name in ("notify", "stats", "audit"):
        marks = [line for line in dashboard.feed if line.startswith(name)]
        assert [mark.split()[1] for mark in marks] == ["started", "done"]
