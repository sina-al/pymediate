"""Narrow outbound ports required only by the refund-order use case."""

from typing import Protocol, runtime_checkable

from shop.domain.entities.orders import Order


@runtime_checkable
class RefundOrderDbGateway(Protocol):
    """Load and update the one order being refunded."""

    async def get_order(self, order_id: int) -> Order: ...
    async def replace_order(self, order: Order) -> None: ...


@runtime_checkable
class RefundOrderPaymentGateway(Protocol):
    """Refund part or all of an order payment."""

    async def refund(self, order_id: int, amount_pence: int) -> None: ...


@runtime_checkable
class RefundOrderMailer(Protocol):
    """Send the refund confirmation."""

    async def send(self, recipient: str, subject: str) -> None: ...
