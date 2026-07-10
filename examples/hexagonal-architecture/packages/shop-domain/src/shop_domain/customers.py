"""Customers: who buys, and the store credit their refunds can accrue."""

from dataclasses import dataclass


@dataclass
class Customer:
    """A registered customer."""

    customer_id: str
    name: str
    email: str
    store_credit_cents: int = 0
