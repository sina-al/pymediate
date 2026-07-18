"""Narrow outbound ports required only by the cancel-order use case."""

from typing import Protocol, runtime_checkable

from shop.domain.entities.orders import Order, OrderItem


@runtime_checkable
class CancelOrderDbGateway(Protocol):
    """Load and update the one order being cancelled."""

    async def get_order(self, order_id: int) -> Order: ...
    async def replace_order(self, order: Order) -> None: ...


@runtime_checkable
class CancelOrderInventory(Protocol):
    """Release stock reserved by a cancelled order."""

    async def release(self, items: tuple[OrderItem, ...]) -> None: ...


@runtime_checkable
class CancelOrderPaymentGateway(Protocol):
    """Void a payment authorization for a cancelled order."""

    async def void(self, order_id: int, amount_pence: int) -> None: ...


@runtime_checkable
class CancelOrderMailer(Protocol):
    """Send the order cancellation confirmation."""

    async def send(self, recipient: str, subject: str) -> None: ...
