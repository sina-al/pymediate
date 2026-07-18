"""Local payment adapter."""

from dataclasses import dataclass, field

from shop.ports.orders.cancel_order import CancelOrderPaymentGateway
from shop.ports.orders.create_order import CreateOrderPaymentGateway
from shop.ports.orders.refund_order import RefundOrderPaymentGateway


@dataclass
class EphemeralPayments(
    CreateOrderPaymentGateway, CancelOrderPaymentGateway, RefundOrderPaymentGateway
):
    """Record payment commands in place of a credentialed provider."""

    charges: list[tuple[int, int]] = field(default_factory=list)
    refunds: list[tuple[int, int]] = field(default_factory=list)
    voids: list[tuple[int, int]] = field(default_factory=list)

    async def charge(self, order_id: int, amount_pence: int) -> None:
        self.charges.append((order_id, amount_pence))

    async def refund(self, order_id: int, amount_pence: int) -> None:
        self.refunds.append((order_id, amount_pence))

    async def void(self, order_id: int, amount_pence: int) -> None:
        self.voids.append((order_id, amount_pence))
