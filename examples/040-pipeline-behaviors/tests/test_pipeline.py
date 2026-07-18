"""Tests for the pipeline-behaviors example — asserts stack ordering and the short-circuit."""

import pytest
from pymediate import Mediator

from taskboard.app import build_mediator
from taskboard.domain import (
    AccessDeniedError,
    AddTask,
    CompleteTask,
    FakeCache,
    GetTask,
    ListOpenTasks,
    Principal,
    TaskNotFoundError,
    TaskStore,
)


@pytest.fixture
def store() -> TaskStore:
    return TaskStore()


@pytest.fixture
def cache() -> FakeCache:
    return FakeCache()


@pytest.fixture
def trace() -> list[str]:
    return []


@pytest.fixture
def mediator(store: TaskStore, cache: FakeCache, trace: list[str]) -> Mediator:
    return build_mediator(store=store, cache=cache, trace=trace)


async def test_command_runs_the_full_stack_in_registration_order(
    mediator: Mediator, trace: list[str]
) -> None:
    await mediator.send(AddTask(title="Buy groceries"))

    # Outermost-first: logging wraps authorization and the transaction-boundary trace.
    assert trace == [
        "log:enter AddTask",
        "authorization AddTask",
        "transaction:enter",
        "transaction:exit",
        "log:exit AddTask",
    ]


async def test_query_skips_command_only_behaviors(mediator: Mediator, trace: list[str]) -> None:
    task = await mediator.send(AddTask(title="read me"))
    trace.clear()

    await mediator.send(GetTask(task_id=task.task_id))

    # No authorization or transaction boundary: those behaviors select Command, not Query.
    assert trace == ["log:enter GetTask", "cache:miss GetTask", "log:exit GetTask"]


async def test_cache_hit_short_circuits_the_handler(
    mediator: Mediator, store: TaskStore, trace: list[str]
) -> None:
    task = await mediator.send(AddTask(title="cache me"))
    trace.clear()

    first = await mediator.send(GetTask(task_id=task.task_id))
    second = await mediator.send(GetTask(task_id=task.task_id))

    assert first == second
    # The handler ran once across two sends: the second was served from cache.
    assert store.reads == 1
    assert trace == [
        "log:enter GetTask",
        "cache:miss GetTask",
        "log:exit GetTask",
        "log:enter GetTask",
        "cache:hit GetTask",  # next() never called — the handler is skipped
        "log:exit GetTask",
    ]


async def test_should_apply_skips_uncacheable_query(mediator: Mediator, trace: list[str]) -> None:
    await mediator.send(AddTask(title="volatile"))
    trace.clear()

    # ListOpenTasks is uncacheable, so should_apply() drops the caching behavior entirely.
    await mediator.send(ListOpenTasks())
    await mediator.send(ListOpenTasks())

    assert trace == [
        "log:enter ListOpenTasks",
        "log:exit ListOpenTasks",
        "log:enter ListOpenTasks",
        "log:exit ListOpenTasks",
    ]


async def test_logging_is_universal(mediator: Mediator, trace: list[str]) -> None:
    task = await mediator.send(AddTask(title="anything"))
    await mediator.send(GetTask(task_id=task.task_id))
    await mediator.send(ListOpenTasks())

    enters = [e for e in trace if e.startswith("log:enter")]
    assert enters == ["log:enter AddTask", "log:enter GetTask", "log:enter ListOpenTasks"]


async def test_unauthorized_command_is_rejected_before_the_handler(
    store: TaskStore, trace: list[str]
) -> None:
    guest = Principal("guest", can_write=False)
    mediator = build_mediator(store=store, trace=trace, principal=guest)

    with pytest.raises(AccessDeniedError):
        await mediator.send(AddTask(title="denied"))

    assert store.tasks == {}  # the handler never ran
    # Authorization runs before the transaction boundary, so no transaction marker is added.
    assert trace == ["log:enter AddTask", "log:exit AddTask"]


async def test_transaction_boundary_records_handler_error(
    mediator: Mediator, trace: list[str]
) -> None:
    with pytest.raises(TaskNotFoundError):
        await mediator.send(CompleteTask(task_id=999))

    assert trace == [
        "log:enter CompleteTask",
        "authorization CompleteTask",
        "transaction:enter",
        "transaction:error",
        "log:exit CompleteTask",
    ]
