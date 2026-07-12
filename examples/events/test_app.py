"""Tests for the events example — the examples contract's `uv run pytest` entrypoint."""

import pytest
from pymediate import Mediator

from app import (
    AddTask,
    CompleteTask,
    Task,
    TaskCompleted,
    TaskNotFoundError,
    TaskStore,
    build_mediator,
)


@pytest.fixture
def store() -> TaskStore:
    return TaskStore()


@pytest.fixture
def audit() -> list[str]:
    return []


@pytest.fixture
def outbox() -> list[str]:
    return []


@pytest.fixture
def counts() -> dict[str, int]:
    return {}


@pytest.fixture
def mediator(
    store: TaskStore, audit: list[str], outbox: list[str], counts: dict[str, int]
) -> Mediator:
    return build_mediator(store, audit, outbox, counts)


async def test_publish_notifies_every_handler(
    mediator: Mediator, audit: list[str], outbox: list[str], counts: dict[str, int]
) -> None:
    await mediator.publish(TaskCompleted(task_id=1, title="Ship it"))

    assert audit == ["task 1 completed: Ship it"]
    assert outbox == ["Nice work! 'Ship it' is done."]
    assert counts == {"completed": 1}


async def test_each_handler_fires_once_per_publish(
    mediator: Mediator, counts: dict[str, int]
) -> None:
    await mediator.publish(TaskCompleted(task_id=1, title="first"))
    await mediator.publish(TaskCompleted(task_id=2, title="second"))

    assert counts == {"completed": 2}


async def test_event_carries_the_completed_task_details(
    mediator: Mediator, audit: list[str]
) -> None:
    await mediator.publish(TaskCompleted(task_id=42, title="Write the release notes"))

    assert audit == ["task 42 completed: Write the release notes"]


async def test_send_still_returns_typed_responses(mediator: Mediator) -> None:
    task = await mediator.send(AddTask(title="Buy groceries"))
    completed = await mediator.send(CompleteTask(task_id=task.task_id))

    assert isinstance(task, Task)
    assert task.task_id == 1
    assert completed.done is True


async def test_complete_unknown_task_raises(mediator: Mediator) -> None:
    with pytest.raises(TaskNotFoundError):
        await mediator.send(CompleteTask(task_id=999))


async def test_completing_a_task_then_publishing_records_it(
    mediator: Mediator, audit: list[str], outbox: list[str]
) -> None:
    task = await mediator.send(AddTask(title="Tidy the kitchen"))
    completed = await mediator.send(CompleteTask(task_id=task.task_id))
    await mediator.publish(TaskCompleted(task_id=completed.task_id, title=completed.title))

    assert audit == ["task 1 completed: Tidy the kitchen"]
    assert outbox == ["Nice work! 'Tidy the kitchen' is done."]
