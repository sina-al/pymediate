"""Typer commands entering the customers feature module."""

import asyncio
from typing import Annotated

import typer

from shop.application.customers.adjust_store_credit import AdjustStoreCreditRequest
from shop.application.customers.open_customer_account import OpenCustomerAccountRequest
from shop.cli.context import get_context

customers = typer.Typer(
    help="Manage customer accounts and store credit.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


@customers.command("open")
def open_account(
    context: typer.Context,
    customer: Annotated[int, typer.Option("--customer", min=1, help="Customer identifier.")],
) -> None:
    """Open a customer account with a zero store-credit balance."""
    cli = get_context(context)
    result = asyncio.run(cli.send(OpenCustomerAccountRequest(customer)))
    cli.success(
        "Customer account opened",
        {
            "Customer": f"#{result.customer_id}",
            "Balance": f"£{result.store_credit_pence / 100:.2f}",
        },
    )


@customers.command("credit")
def credit(
    context: typer.Context,
    customer: Annotated[int, typer.Option("--customer", help="Customer identifier.")],
    amount: Annotated[int, typer.Option("--amount", min=1, help="Credit amount in pence.")],
) -> None:
    """Add a positive amount to a customer's store-credit balance."""
    cli = get_context(context)
    result = asyncio.run(cli.send(AdjustStoreCreditRequest(customer, amount)))
    cli.success(
        "Store credit updated",
        {
            "Customer": f"#{result.customer_id}",
            "Balance": f"£{result.store_credit_pence / 100:.2f}",
        },
    )
