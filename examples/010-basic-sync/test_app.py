"""Tests for the 010-basic-sync example — the examples contract's `uv run pytest` entrypoint."""

import pytest
from pymediate.sync import Mediator

from app import AddTask, Task, TaskStore, build_mediator


@pytest.fixture
def store() -> TaskStore:
    return TaskStore()


@pytest.fixture
def mediator(store: TaskStore) -> Mediator:
    return build_mediator(store)


def test_send_returns_created_task(mediator: Mediator) -> None:
    task = mediator.send(AddTask(title="Buy groceries"))

    assert isinstance(task, Task)
    assert task.task_id == 1
    assert task.title == "Buy groceries"
    assert task.done is False


def test_ids_increment(mediator: Mediator) -> None:
    first = mediator.send(AddTask(title="first"))
    second = mediator.send(AddTask(title="second"))

    assert (first.task_id, second.task_id) == (1, 2)


def test_handler_writes_through_to_the_store(store: TaskStore, mediator: Mediator) -> None:
    mediator.send(AddTask(title="visible in the store"))

    assert store.tasks[1].title == "visible in the store"
