"""Ports that replace the article's customers-to-orders circular import."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class CloseCustomerAccountDbGateway(Protocol):
    """Delete one existing customer account without exposing database APIs."""

    async def delete_customer(self, customer_id: int) -> None: ...


@runtime_checkable
class CustomerOpenOrders(Protocol):
    """Answer the one orders-context question required before closure."""

    async def has_open_orders(self, customer_id: int) -> bool: ...
