"""Tests for the asyncclick adapter — exercises the whole core through its CliRunner."""

import pytest
from asyncclick.testing import CliRunner

from taskboard.adapters.cli import cli


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


async def test_add_task_echoes_created_task(runner: CliRunner) -> None:
    result = await runner.invoke(cli, ["add", "Buy groceries"])

    assert result.exit_code == 0
    assert result.output == "Added task 1: Buy groceries\n"


async def test_ids_increment_within_one_invocation(runner: CliRunner) -> None:
    result = await runner.invoke(cli, ["add", "first", "add", "second"])

    assert result.exit_code == 0
    assert result.output == "Added task 1: first\nAdded task 2: second\n"


async def test_complete_task_marks_done(runner: CliRunner) -> None:
    result = await runner.invoke(cli, ["add", "Ship it", "complete", "1"])

    assert result.exit_code == 0
    assert "Completed task 1: Ship it" in result.output


async def test_complete_unknown_task_fails_with_error(runner: CliRunner) -> None:
    result = await runner.invoke(cli, ["complete", "999"])

    assert result.exit_code == 1
    assert "Error: No task with id 999" in result.stderr


async def test_list_open_tasks_excludes_done(runner: CliRunner) -> None:
    result = await runner.invoke(
        cli, ["add", "keep me", "add", "finish me", "complete", "2", "list"]
    )

    assert result.exit_code == 0
    assert result.output.splitlines()[-1] == "[1] keep me"


async def test_each_invocation_gets_its_own_store(runner: CliRunner) -> None:
    await runner.invoke(cli, ["add", "gone next time"])

    result = await runner.invoke(cli, ["list"])

    assert result.exit_code == 0
    assert result.output == ""
