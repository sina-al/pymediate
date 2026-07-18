"""Typer commands entering the orders feature module."""

import asyncio
from typing import Annotated, Literal

import typer

from shop.application.orders.create_order import CreateOrderRequest
from shop.application.orders.export_orders import ExportOrdersRequest
from shop.application.orders.get_order_history import GetOrderHistoryRequest
from shop.application.orders.request_order_export import RequestOrderExportRequest
from shop.cli.context import get_context
from shop.domain.entities.orders import OrderItem
from shop.domain.errors.orders import InvalidQuantityError

orders = typer.Typer(
    help="Place orders and export order history.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


def _parse_item(value: str) -> OrderItem:
    """Parse a human-friendly ``SKU:QUANTITY`` order line."""
    sku, separator, quantity = value.partition(":")
    if not separator:
        raise typer.BadParameter("use SKU:QUANTITY, for example book:2")
    try:
        return OrderItem(sku=sku, quantity=int(quantity))
    except (ValueError, InvalidQuantityError) as error:
        raise typer.BadParameter(str(error)) from error


@orders.command()
def place(
    context: typer.Context,
    customer: Annotated[int, typer.Option("--customer", help="Customer identifier.")],
    items: Annotated[
        list[str],
        typer.Argument(
            help="One or more [bold]SKU:QUANTITY[/] lines, for example [cyan]book:2 mug:1[/].",
        ),
    ],
) -> None:
    """Place an order from one or more SKU:QUANTITY items."""
    cli = get_context(context)
    order = asyncio.run(
        cli.send(CreateOrderRequest(customer, tuple(_parse_item(item) for item in items)))
    )
    cli.success(
        "Order placed",
        {
            "Order": f"#{order.order_id}",
            "Total": f"£{order.total_pence / 100:.2f}",
            "Status": order.status,
        },
    )


@orders.command("export")
def export_orders(
    context: typer.Context,
    customer: Annotated[int, typer.Option("--customer", help="Customer identifier.")],
    export_format: Annotated[
        Literal["csv", "jsonl"],
        typer.Option("--format", help="Document format to generate."),
    ] = "csv",
) -> None:
    """Create an order export immediately in this process."""
    cli = get_context(context)
    result = asyncio.run(cli.send(ExportOrdersRequest(customer, export_format)))
    cli.success(
        "Export ready",
        {"Location": result.url, "Orders": str(result.rows), "Format": export_format.upper()},
    )


@orders.command("request-export")
def request_export(
    context: typer.Context,
    customer: Annotated[int, typer.Option("--customer", help="Customer identifier.")],
    export_format: Annotated[
        Literal["csv", "jsonl"],
        typer.Option("--format", help="Document format for the worker to generate."),
    ] = "csv",
) -> None:
    """Queue an order export for the worker."""
    cli = get_context(context)
    job = asyncio.run(cli.send(RequestOrderExportRequest(customer, export_format)))
    cli.success(
        "Export queued",
        {
            "Job": str(job.job_id),
            "Format": export_format.upper(),
            "Next": "shop-worker consumes it",
        },
    )


@orders.command()
def history(
    context: typer.Context,
    order: Annotated[int, typer.Option("--order", min=1, help="Order identifier.")],
) -> None:
    """Show the stable public history projected for one order."""
    cli = get_context(context)
    result = asyncio.run(cli.send(GetOrderHistoryRequest(order)))
    cli.table(
        f"Order #{result.order_id} history",
        ("Event", "Occurred", "Amount", "Status"),
        (
            (
                entry.kind.replace("-", " ").title(),
                entry.occurred_at.isoformat(timespec="seconds"),
                _money(entry.amount_pence),
                entry.status or "—",
            )
            for entry in result.entries
        ),
        empty="No public history entries",
    )


def _money(value: int | None) -> str:
    return "—" if value is None else f"£{value / 100:.2f}"
