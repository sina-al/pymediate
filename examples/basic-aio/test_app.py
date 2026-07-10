"""Tests for the basic-aio example — the examples contract's `uv run pytest` entrypoint."""

import pytest
from pymediate.aio import Mediator

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
def audit_log() -> list[str]:
    return []


@pytest.fixture
def mediator(store: TaskStore, audit_log: list[str]) -> Mediator:
    return build_mediator(store, audit_log)


async def test_add_task_returns_created_task(mediator: Mediator) -> None:
    task = await mediator.send(AddTask(title="Buy groceries"))

    assert isinstance(task, Task)
    assert task.task_id == 1
    assert task.title == "Buy groceries"
    assert task.done is False


async def test_ids_increment(mediator: Mediator) -> None:
    first = await mediator.send(AddTask(title="first"))
    second = await mediator.send(AddTask(title="second"))

    assert (first.task_id, second.task_id) == (1, 2)


async def test_complete_task_marks_done(mediator: Mediator) -> None:
    task = await mediator.send(AddTask(title="Ship it"))

    completed = await mediator.send(CompleteTask(task_id=task.task_id))

    assert completed.done is True


async def test_complete_unknown_task_raises(mediator: Mediator) -> None:
    with pytest.raises(TaskNotFoundError):
        await mediator.send(CompleteTask(task_id=999))


async def test_list_open_tasks_excludes_done(mediator: Mediator) -> None:
    keep = await mediator.send(AddTask(title="keep me"))
    done = await mediator.send(AddTask(title="finish me"))
    await mediator.send(CompleteTask(task_id=done.task_id))

    open_tasks = await mediator.send(ListOpenTasks())

    assert [t.task_id for t in open_tasks] == [keep.task_id]


async def test_audit_trail_records_mutations(mediator: Mediator, audit_log: list[str]) -> None:
    task = await mediator.send(AddTask(title="audited"))
    await mediator.send(CompleteTask(task_id=task.task_id))

    assert audit_log == ["AddTask: task 1", "CompleteTask: task 1"]


async def test_audit_trail_skips_reads(mediator: Mediator, audit_log: list[str]) -> None:
    await mediator.send(ListOpenTasks())

    assert audit_log == []
