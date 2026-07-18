"""Place an order without knowing which adapter fulfils its outbound ports."""

from asyncio import CancelledError
from dataclasses import dataclass

from pymediate import Request, RequestHandler

from shop.application.integration_contracts import InvoiceRequestedV1, OrderConfirmationRequestedV1
from shop.application.outbox_messages import outbox_message
from shop.domain.entities.orders import Order, OrderItem, OrderLine
from shop.domain.errors.orders import EmptyOrderError
from shop.domain.events.orders import OrderPlacedEvent
from shop.ports.audit import DomainEventJournal
from shop.ports.orders.create_order import (
    CreateOrderClock,
    CreateOrderDbGateway,
    CreateOrderInventory,
    CreateOrderPaymentGateway,
    ProductCatalogue,
)
from shop.ports.unit_of_work import UnitOfWork


@dataclass(frozen=True)
class CreateOrderResponse:
    """Public result of placing an order with fewer fields than ``Order``."""

    order_id: int
    customer_id: int
    total_pence: int
    refunded_pence: int
    status: str

    @classmethod
    def from_domain(cls, order: Order) -> "CreateOrderResponse":
        """Select the fields allowed to cross the application boundary."""
        return cls(
            order.order_id,
            order.customer_id,
            order.total_pence,
            order.refunded_pence,
            order.status.value,
        )


@dataclass(frozen=True)
class CreateOrderRequest(Request[CreateOrderResponse]):
    """Describe the intent to place an order."""

    customer_id: int
    items: tuple[OrderItem, ...]


class CreateOrderHandler(RequestHandler[CreateOrderRequest]):
    """Apply order rules and coordinate the catalogue and repository ports."""

    def __init__(
        self,
        catalogue: ProductCatalogue,
        clock: CreateOrderClock,
        unit: UnitOfWork,
        database: CreateOrderDbGateway,
        inventory: CreateOrderInventory,
        payments: CreateOrderPaymentGateway,
        journal: DomainEventJournal,
    ) -> None:
        self._catalogue = catalogue
        self._clock = clock
        self._unit = unit
        self._database = database
        self._inventory = inventory
        self._payments = payments
        self._journal = journal

    async def __call__(self, request: CreateOrderRequest) -> CreateOrderResponse:
        if not request.items:
            raise EmptyOrderError()

        products = [await self._catalogue.get_product(item.sku) for item in request.items]
        lines = tuple(
            OrderLine(product.sku, item.quantity, product.price_pence)
            for item, product in zip(request.items, products, strict=True)
        )
        order = Order.place(
            await self._database.next_order_identity(),
            request.customer_id,
            lines,
            self._clock.today(),
        )
        await self._inventory.reserve(request.items)
        try:
            await self._payments.charge(order.order_id, order.total_pence)
        except (Exception, CancelledError) as error:
            await self._compensate(order, request.items, error, refund_payment=False)
            raise

        try:
            async with self._unit:
                await self._database.insert_order(order)
                placed = OrderPlacedEvent(order.order_id, order.customer_id, order.total_pence)
                await self._journal.append(placed)
                await self._database.insert_outbox_message(
                    outbox_message(OrderConfirmationRequestedV1(order.order_id, order.customer_id))
                )
                await self._database.insert_outbox_message(
                    outbox_message(
                        InvoiceRequestedV1(
                            order.order_id,
                            order.customer_id,
                            order.total_pence,
                        )
                    )
                )
        except (Exception, CancelledError) as error:
            await self._compensate(order, request.items, error, refund_payment=True)
            raise
        return CreateOrderResponse.from_domain(order)

    async def _compensate(
        self,
        order: Order,
        items: tuple[OrderItem, ...],
        original: BaseException,
        *,
        refund_payment: bool,
    ) -> None:
        """Attempt every applicable compensation without losing the original failure."""
        failures: list[BaseException] = [original]
        if refund_payment:
            try:
                await self._payments.refund(order.order_id, order.total_pence)
            except (Exception, CancelledError) as error:
                failures.append(error)
        try:
            await self._inventory.release(items)
        except (Exception, CancelledError) as error:
            failures.append(error)
        if len(failures) > 1:
            raise BaseExceptionGroup("Order creation compensation failed", failures) from original
