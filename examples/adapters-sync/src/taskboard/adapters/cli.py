"""Click adapter: a command-line interface over the same core.

The group chains, so one invocation can run a whole session against one in-memory
store: ``python cli.py add "Buy milk" add "Ship it" complete 1 list``. The core's
TaskNotFoundError maps to click's error convention (message on stderr, exit code 1)
via ClickException.
"""

import click
from pymediate.sync import Mediator

from taskboard.core import AddTask, CompleteTask, ListOpenTasks, TaskNotFoundError, build_mediator


@click.group(chain=True)
@click.pass_context
def cli(ctx: click.Context) -> None:
    """Task board CLI. Chain commands: add "Buy milk" complete 1 list."""
    ctx.obj = build_mediator()


@cli.command()
@click.argument("title")
@click.pass_obj
def add(mediator: Mediator, title: str) -> None:
    """Add a task with the given TITLE."""
    task = mediator.send(AddTask(title=title))
    click.echo(f"Added task {task.task_id}: {task.title}")


@cli.command()
@click.argument("task_id", type=int)
@click.pass_obj
def complete(mediator: Mediator, task_id: int) -> None:
    """Mark task TASK_ID as done."""
    try:
        task = mediator.send(CompleteTask(task_id=task_id))
    except TaskNotFoundError as error:
        raise click.ClickException(str(error)) from error
    click.echo(f"Completed task {task.task_id}: {task.title}")


@cli.command(name="list")
@click.pass_obj
def list_open(mediator: Mediator) -> None:
    """List open tasks."""
    for task in mediator.send(ListOpenTasks()):
        click.echo(f"[{task.task_id}] {task.title}")


if __name__ == "__main__":
    cli()
