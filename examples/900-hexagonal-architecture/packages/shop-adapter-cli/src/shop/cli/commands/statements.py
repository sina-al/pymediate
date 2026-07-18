"""Typer commands entering the statements feature module."""

import asyncio
from typing import Annotated, Literal

import typer

from shop.application.statements.create_monthly_statement import (
    CreateMonthlyStatementRequest,
)
from shop.cli.context import get_context

statements = typer.Typer(
    help="Create customer statements.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


@statements.command()
def create(
    context: typer.Context,
    customer: Annotated[int, typer.Option("--customer", help="Customer identifier.")],
    year: Annotated[int, typer.Option("--year", help="Four-digit statement year.")],
    month: Annotated[int, typer.Option("--month", min=1, max=12, help="Month from 1 to 12.")],
    currency: Annotated[
        Literal["GBP", "EUR", "USD"],
        typer.Option("--currency", help="Display currency."),
    ] = "GBP",
) -> None:
    """Create a customer's monthly statement."""
    cli = get_context(context)
    result = asyncio.run(cli.send(CreateMonthlyStatementRequest(customer, year, month, currency)))
    cli.success(
        "Statement ready",
        {
            "Location": result.document_url,
            "Period": f"{year:04d}-{month:02d}",
            "Currency": currency,
        },
    )
