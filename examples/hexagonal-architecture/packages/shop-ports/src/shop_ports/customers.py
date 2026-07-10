"""What the application needs from wherever customers are kept."""

from typing import Protocol

from shop_domain.customers import Customer


class CustomerRepository(Protocol):
    """Persistence for customers, including their store credit balance."""

    def add(self, customer: Customer) -> None:
        """Store a new customer."""
        ...

    def get(self, customer_id: str) -> Customer | None:
        """Fetch a customer by id, or None if they don't exist."""
        ...

    def credit(self, customer_id: str, amount_cents: int) -> Customer | None:
        """Add store credit and return the updated customer, or None if unknown."""
        ...
