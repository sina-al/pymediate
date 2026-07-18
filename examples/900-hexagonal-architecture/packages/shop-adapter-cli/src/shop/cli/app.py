"""Typer command-line adapter for the Shop application."""

import os
from pathlib import Path
from typing import Annotated

import typer

from shop.bindings.loading import create_application_container, load_wiring
from shop.cli.commands import customers, invoices, orders, statements
from shop.cli.context import CliContext

app = typer.Typer(
    name="shop",
    help="[bold cyan]Shop[/] — command-line interface for the hexagonal architecture example.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


@app.callback()
def main_callback(
    context: typer.Context,
    wiring: Annotated[
        Path | None,
        typer.Option(
            "--wiring",
            metavar="PATH",
            help="Override SHOP_WIRING with a YAML provider manifest for this invocation.",
        ),
    ] = None,
) -> None:
    """Drive Shop use cases through PyMediate."""
    if context.obj is None:
        selected = load_wiring(wiring)
        container = create_application_container(selected)
        context.obj = CliContext(container.mediator(), wiring=selected)


app.add_typer(orders, name="orders")
app.add_typer(customers, name="customers")
app.add_typer(invoices, name="invoices")
app.add_typer(statements, name="statements")

# Kept as the test-friendly command object name used by the example's integration tests.
cli = app


def main() -> None:
    """Run the Shop command-line application."""
    os.environ.setdefault("OTEL_SDK_DISABLED", "true")
    app(prog_name="shop")
