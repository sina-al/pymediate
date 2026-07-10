"""Tests for the basic-sync example — the examples contract's `uv run pytest` entrypoint."""

import pytest
from pymediate import Mediator

from app import (
    AddTask,
    CompleteTask,
    ListOpenTasks,
    Task,
    TaskNotFoundError,
    TaskStore,
    build_mediator,
)


@pytest.fixture
def store() -> TaskStore:
    return TaskStore()


@pytest.fixture
def mediator(store: TaskStore) -> Mediator:
    return build_mediator(store)


def test_add_task_returns_created_task(mediator: Mediator) -> None:
    task = mediator.send(AddTask(title="Buy groceries"))

    assert isinstance(task, Task)
    assert task.task_id == 1
    assert task.title == "Buy groceries"
    assert task.done is False


def test_ids_increment(mediator: Mediator) -> None:
    first = mediator.send(AddTask(title="first"))
    second = mediator.send(AddTask(title="second"))

    assert (first.task_id, second.task_id) == (1, 2)


def test_complete_task_marks_done(mediator: Mediator) -> None:
    task = mediator.send(AddTask(title="Ship it"))

    completed = mediator.send(CompleteTask(task_id=task.task_id))

    assert completed.done is True


def test_complete_unknown_task_raises(mediator: Mediator) -> None:
    with pytest.raises(TaskNotFoundError):
        mediator.send(CompleteTask(task_id=999))


def test_list_open_tasks_excludes_done(mediator: Mediator) -> None:
    keep = mediator.send(AddTask(title="keep me"))
    done = mediator.send(AddTask(title="finish me"))
    mediator.send(CompleteTask(task_id=done.task_id))

    open_tasks = mediator.send(ListOpenTasks())

    assert [t.task_id for t in open_tasks] == [keep.task_id]


def test_handlers_share_the_store(store: TaskStore, mediator: Mediator) -> None:
    mediator.send(AddTask(title="visible in the store"))

    assert store.tasks[1].title == "visible in the store"
