"""The CLI doorway: Typer commands that build requests and send them.

The composition root hands this module a way to open a runtime (a finished mediator
plus whatever teardown its adapters need); each command opens one, sends its request,
and prints the result. Support's quarterly ask, done in a doorway.
"""

from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from typing import Annotated

import typer
from pymediate import Mediator

from shop_core.customers import RegisterCustomer
from shop_core.errors import ShopError
from shop_core.orders import CancelOrder, ExportOrders, PlaceOrder, RefundOrder
from shop_domain.orders import LineItem

RuntimeFactory = Callable[[], AbstractContextManager[Mediator]]


def _parse_item(raw: str) -> LineItem:
    sku, quantity, unit_price_cents = raw.split(":")
    return LineItem(sku=sku, quantity=int(quantity), unit_price_cents=int(unit_price_cents))


@contextmanager
def _translating_errors() -> Iterator[None]:
    """The CLI's half of error mapping: domain errors become stderr + exit code 1."""
    try:
        yield
    except ShopError as error:
        typer.secho(f"Error: {error}", err=True, fg=typer.colors.RED)
        raise typer.Exit(code=1) from error


def build_cli(runtime: RuntimeFactory) -> typer.Typer:
    """Build the CLI around a runtime factory supplied by a composition root."""
    cli = typer.Typer(help="The shop, from a terminal.", no_args_is_help=True)

    @cli.command()
    def register_customer(name: str, email: str) -> None:
        """Register a customer and print their id."""
        with _translating_errors(), runtime() as mediator:
            customer = mediator.send(RegisterCustomer(name=name, email=email))
            typer.echo(f"Registered {customer.name} ({customer.customer_id})")

    @cli.command()
    def place_order(
        customer_id: str,
        item: Annotated[
            list[str], typer.Option(help="Repeatable, as sku:quantity:unit_price_cents")
        ],
    ) -> None:
        """Place an order for a customer."""
        with _translating_errors(), runtime() as mediator:
            order = mediator.send(
                PlaceOrder(customer_id=customer_id, items=[_parse_item(raw) for raw in item])
            )
            typer.echo(f"Placed order {order.order_id} for {order.total_cents} cents")

    @cli.command()
    def cancel_order(order_id: str) -> None:
        """Cancel a placed order."""
        with _translating_errors(), runtime() as mediator:
            order = mediator.send(CancelOrder(order_id=order_id))
            typer.echo(f"Cancelled order {order.order_id}")

    @cli.command()
    def refund_order(
        order_id: str,
        store_credit: Annotated[bool, typer.Option(help="Refund to store credit instead")] = False,
    ) -> None:
        """Refund a placed order."""
        with _translating_errors(), runtime() as mediator:
            refund = mediator.send(RefundOrder(order_id=order_id, to_store_credit=store_credit))
            typer.echo(
                f"Refunded {refund.amount_cents} cents via {refund.method.value} "
                f"({refund.reference})"
            )

    @cli.command()
    def export(customer_id: str, fmt: str = "csv") -> None:
        """Export a customer's orders — the same request the worker sends."""
        with _translating_errors(), runtime() as mediator:
            result = mediator.send(ExportOrders(customer_id=customer_id, fmt=fmt))
            typer.echo(f"Exported {result.rows} orders to {result.url}")

    @cli.command()
    def demo() -> None:
        """Run a full scripted session: register, buy, refund, export."""
        with _translating_errors(), runtime() as mediator:
            customer = mediator.send(RegisterCustomer(name="Ada", email="ada@example.com"))
            typer.echo(f"Registered {customer.name} ({customer.customer_id})")

            order = mediator.send(
                PlaceOrder(
                    customer_id=customer.customer_id,
                    items=[LineItem(sku="widget", quantity=2, unit_price_cents=1999)],
                )
            )
            typer.echo(f"Placed order {order.order_id} for {order.total_cents} cents")

            refund = mediator.send(RefundOrder(order_id=order.order_id, to_store_credit=True))
            typer.echo(f"Refunded {refund.amount_cents} cents via {refund.method.value}")

            result = mediator.send(ExportOrders(customer_id=customer.customer_id))
            typer.echo(f"Exported {result.rows} orders to {result.url}")

    return cli
