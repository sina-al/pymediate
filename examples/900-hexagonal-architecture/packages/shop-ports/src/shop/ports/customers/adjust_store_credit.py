"""Port owned by the customers use case that adjusts store credit."""

from typing import Protocol, runtime_checkable

from shop.domain.entities.customers import CustomerAccount


@runtime_checkable
class AdjustStoreCreditDbGateway(Protocol):
    """Load and save only the customer account being credited."""

    async def get_customer(self, customer_id: int) -> CustomerAccount: ...
    async def replace_customer(self, customer: CustomerAccount) -> None: ...
