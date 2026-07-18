"""Refund an order through application-owned persistence, payment, and mail ports."""

from dataclasses import dataclass

from pymediate import Request, RequestHandler

from shop.domain.entities.orders import Order
from shop.domain.events.orders import OrderRefundedEvent
from shop.ports.audit import DomainEventJournal
from shop.ports.orders.refund_order import (
    RefundOrderDbGateway,
    RefundOrderMailer,
    RefundOrderPaymentGateway,
)
from shop.ports.unit_of_work import UnitOfWork


@dataclass(frozen=True)
class RefundOrderResponse:
    """Public refund result, independent of the persisted aggregate."""

    order_id: int
    customer_id: int
    total_pence: int
    refunded_pence: int
    status: str

    @classmethod
    def from_domain(cls, order: Order) -> "RefundOrderResponse":
        """Select the fields allowed to cross the application boundary."""
        return cls(
            order.order_id,
            order.customer_id,
            order.total_pence,
            order.refunded_pence,
            order.status.value,
        )


@dataclass(frozen=True)
class RefundOrderRequest(Request[RefundOrderResponse]):
    """Describe a refund."""

    order_id: int
    amount_pence: int


class RefundOrderHandler(RequestHandler[RefundOrderRequest]):
    """Refund one order without knowing the payment or database vendors."""

    def __init__(
        self,
        unit: UnitOfWork,
        database: RefundOrderDbGateway,
        journal: DomainEventJournal,
        payments: RefundOrderPaymentGateway,
        mailer: RefundOrderMailer,
    ) -> None:
        self._unit = unit
        self._database = database
        self._journal = journal
        self._payments = payments
        self._mailer = mailer

    async def __call__(self, request: RefundOrderRequest) -> RefundOrderResponse:
        async with self._unit:
            order = await self._database.get_order(request.order_id)
            refunded = order.refund(request.amount_pence)
            await self._database.replace_order(refunded)
            event = OrderRefundedEvent(
                order.order_id,
                order.customer_id,
                request.amount_pence,
                refunded.refunded_pence,
                refunded.status.value,
            )
            await self._journal.append(event)
        await self._payments.refund(order.order_id, request.amount_pence)
        await self._mailer.send(
            f"customer-{order.customer_id}@example.com", f"Order {order.order_id} refunded"
        )
        return RefundOrderResponse.from_domain(refunded)
