"""Shared CLI context and terminal presentation primitives."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

import typer
from pymediate import Mediator, Request
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from shop.bindings.wiring import Wiring
from shop.domain.errors import DomainError


def get_context(context: typer.Context) -> CliContext:
    """Return the initialized Shop context for a subcommand."""
    if not isinstance(context.obj, CliContext):
        raise RuntimeError("Shop CLI context was not initialized")
    return context.obj


@dataclass(slots=True)
class CliContext:
    """Dependencies and presentation helpers available to every CLI command."""

    mediator: Mediator
    console: Console | None = None
    wiring: Wiring | None = None

    def _console(self) -> Console:
        """Create the terminal writer lazily so Click's test runner can capture it."""
        return self.console if self.console is not None else Console()

    async def send[ResponseT](self, request: Request[ResponseT]) -> ResponseT:
        """Send a request and render expected business failures for a terminal."""
        try:
            if self.wiring is None:
                return await self.mediator.send(request)
            async with self.wiring.activate("application"):
                return await self.mediator.send(request)
        except DomainError as error:
            self._console().print(
                Panel(
                    f"[bold]{error.detail}[/]",
                    border_style="red",
                    title=f"[bold red]✗ {error.title}[/]",
                )
            )
            raise typer.Exit(code=1) from error

    def success(self, title: str, values: Mapping[str, str]) -> None:
        """Render a compact, colour-coded success card."""
        details = Table.grid(padding=(0, 1))
        details.add_column(style="dim", justify="right")
        details.add_column(style="bold white")
        for label, value in values.items():
            details.add_row(label, value)
        self._console().print(
            Panel.fit(
                details,
                border_style="green",
                title=f"[bold green]✓ {title}[/]",
            )
        )

    def table(
        self,
        title: str,
        columns: Sequence[str],
        rows: Iterable[Sequence[str]],
        *,
        empty: str,
    ) -> None:
        """Render tabular query results with an explicit empty state."""
        values = tuple(rows)
        table = Table(title=title, header_style="bold cyan", border_style="cyan")
        for column in columns:
            table.add_column(column)
        for row in values:
            table.add_row(*row)
        if not values:
            table.add_row(empty, *("—" for _ in columns[1:]), style="dim")
        self._console().print(table)
