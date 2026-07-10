"""What the application needs from wherever orders are kept."""

from typing import Protocol

from shop_domain.orders import Order


class OrderRepository(Protocol):
    """Persistence for orders — implemented by dicts, Postgres, or Neo4j alike."""

    def add(self, order: Order) -> None:
        """Store a new order."""
        ...

    def get(self, order_id: str) -> Order | None:
        """Fetch an order by id, or None if it doesn't exist."""
        ...

    def update(self, order: Order) -> None:
        """Persist changes to an existing order."""
        ...

    def for_customer(self, customer_id: str) -> list[Order]:
        """All of a customer's orders, oldest first."""
        ...
