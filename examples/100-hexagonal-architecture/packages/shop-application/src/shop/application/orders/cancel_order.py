"""Cancel an order without importing inventory, payment, or mail implementations."""

from dataclasses import dataclass

from pymediate import Request, RequestHandler

from shop.domain.entities.orders import Order, OrderItem
from shop.domain.events.orders import OrderCancelledEvent
from shop.ports.audit import DomainEventJournal
from shop.ports.orders.cancel_order import (
    CancelOrderDbGateway,
    CancelOrderInventory,
    CancelOrderMailer,
    CancelOrderPaymentGateway,
)
from shop.ports.unit_of_work import UnitOfWork


@dataclass(frozen=True)
class CancelOrderResponse:
    """Public result of cancellation, independent of the persisted aggregate."""

    order_id: int
    customer_id: int
    total_pence: int
    refunded_pence: int
    status: str

    @classmethod
    def from_domain(cls, order: Order) -> "CancelOrderResponse":
        """Select the fields allowed to cross the application boundary."""
        return cls(
            order.order_id,
            order.customer_id,
            order.total_pence,
            order.refunded_pence,
            order.status.value,
        )


@dataclass(frozen=True)
class CancelOrderRequest(Request[CancelOrderResponse]):
    """Describe the intent to cancel one order."""

    order_id: int


class CancelOrderHandler(RequestHandler[CancelOrderRequest]):
    """Apply cancellation rules and coordinate its narrow outbound ports."""

    def __init__(
        self,
        unit: UnitOfWork,
        database: CancelOrderDbGateway,
        journal: DomainEventJournal,
        inventory: CancelOrderInventory,
        payments: CancelOrderPaymentGateway,
        mailer: CancelOrderMailer,
    ) -> None:
        self._unit = unit
        self._database = database
        self._journal = journal
        self._inventory = inventory
        self._payments = payments
        self._mailer = mailer

    async def __call__(self, request: CancelOrderRequest) -> CancelOrderResponse:
        async with self._unit:
            order = await self._database.get_order(request.order_id)
            cancelled = order.cancel()
            await self._database.replace_order(cancelled)
            event = OrderCancelledEvent(order.order_id, order.customer_id, order.total_pence)
            await self._journal.append(event)

        items = tuple(OrderItem(line.sku, line.quantity) for line in order.lines)
        await self._inventory.release(items)
        await self._payments.void(order.order_id, order.total_pence)
        await self._mailer.send(
            f"customer-{order.customer_id}@example.com", f"Order {order.order_id} cancelled"
        )
        return CancelOrderResponse.from_domain(cancelled)
