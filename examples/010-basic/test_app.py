"""Tests for the 010-basic example — the examples contract's `uv run pytest` entrypoint."""

import pytest
from pymediate import Mediator

from app import AddTask, Task, TaskStore, build_mediator


@pytest.fixture
def store() -> TaskStore:
    return TaskStore()


@pytest.fixture
def mediator(store: TaskStore) -> Mediator:
    return build_mediator(store)


async def test_send_returns_created_task(mediator: Mediator) -> None:
    task = await mediator.send(AddTask(title="Buy groceries"))

    assert isinstance(task, Task)
    assert task.task_id == 1
    assert task.title == "Buy groceries"
    assert task.done is False


async def test_ids_increment(mediator: Mediator) -> None:
    first = await mediator.send(AddTask(title="first"))
    second = await mediator.send(AddTask(title="second"))

    assert (first.task_id, second.task_id) == (1, 2)


async def test_handler_writes_through_to_the_store(store: TaskStore, mediator: Mediator) -> None:
    await mediator.send(AddTask(title="visible in the store"))

    assert store.tasks[1].title == "visible in the store"
