"""asyncclick adapter: a command-line interface whose commands await the async core.

asyncclick is click's async fork, so this file is `examples/adapters-sync/cli.py`
with ``async def`` commands and ``await mediator.send()`` — the CLI framework runs
the event loop. The group chains, so one invocation runs a whole session against one
in-memory store: ``python cli.py add "Buy milk" add "Ship it" complete 1 list``. The
core's TaskNotFoundError maps to click's error convention (message on stderr, exit
code 1) via ClickException.
"""

import asyncclick as click
from pymediate import Mediator

from taskboard.core import AddTask, CompleteTask, ListOpenTasks, TaskNotFoundError, build_mediator


@click.group(chain=True)
@click.pass_context
def cli(ctx: click.Context) -> None:
    """Task board CLI. Chain commands: add "Buy milk" complete 1 list."""
    ctx.obj = build_mediator()


@cli.command()
@click.argument("title")
@click.pass_obj
async def add(mediator: Mediator, title: str) -> None:
    """Add a task with the given TITLE."""
    task = await mediator.send(AddTask(title=title))
    click.echo(f"Added task {task.task_id}: {task.title}")


@cli.command()
@click.argument("task_id", type=int)
@click.pass_obj
async def complete(mediator: Mediator, task_id: int) -> None:
    """Mark task TASK_ID as done."""
    try:
        task = await mediator.send(CompleteTask(task_id=task_id))
    except TaskNotFoundError as error:
        raise click.ClickException(str(error)) from error
    click.echo(f"Completed task {task.task_id}: {task.title}")


@cli.command(name="list")
@click.pass_obj
async def list_open(mediator: Mediator) -> None:
    """List open tasks."""
    for task in await mediator.send(ListOpenTasks()):
        click.echo(f"[{task.task_id}] {task.title}")


if __name__ == "__main__":
    cli()
