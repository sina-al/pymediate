"""Persistence port owned by the open-customer-account use case."""

from typing import Protocol, runtime_checkable

from shop.domain.entities.customers import CustomerAccount


@runtime_checkable
class OpenCustomerAccountDbGateway(Protocol):
    """Insert one new account, rejecting an existing customer identity."""

    async def insert_customer(self, customer: CustomerAccount) -> None: ...
