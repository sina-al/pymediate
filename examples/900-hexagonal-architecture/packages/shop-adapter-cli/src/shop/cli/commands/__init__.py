"""Business-oriented command groups exposed by the Shop CLI."""

from shop.cli.commands.customers import customers
from shop.cli.commands.invoices import invoices
from shop.cli.commands.orders import orders
from shop.cli.commands.statements import statements

__all__ = ["customers", "invoices", "orders", "statements"]
