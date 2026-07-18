"""Close an account without importing the orders context's implementation."""

from dataclasses import dataclass

from pymediate import Request, RequestHandler

from shop.domain.errors.customers import CustomerHasOpenOrdersError
from shop.domain.events.customers import CustomerAccountClosedEvent
from shop.ports.audit import DomainEventJournal
from shop.ports.customers.close_customer_account import (
    CloseCustomerAccountDbGateway,
    CustomerOpenOrders,
)
from shop.ports.unit_of_work import UnitOfWork


@dataclass(frozen=True)
class CloseCustomerAccountResponse:
    """Confirm which customer account was closed."""

    customer_id: int


@dataclass(frozen=True)
class CloseCustomerAccountRequest(Request[CloseCustomerAccountResponse]):
    """Describe the intent to permanently close a customer account."""

    customer_id: int


class CloseCustomerAccountHandler(RequestHandler[CloseCustomerAccountRequest]):
    """Refuse closure while the orders context reports active work."""

    def __init__(
        self,
        unit: UnitOfWork,
        database: CloseCustomerAccountDbGateway,
        orders: CustomerOpenOrders,
        journal: DomainEventJournal,
    ) -> None:
        self._unit = unit
        self._database = database
        self._orders = orders
        self._journal = journal

    async def __call__(self, request: CloseCustomerAccountRequest) -> CloseCustomerAccountResponse:
        if await self._orders.has_open_orders(request.customer_id):
            raise CustomerHasOpenOrdersError(request.customer_id)
        async with self._unit:
            await self._database.delete_customer(request.customer_id)
            event = CustomerAccountClosedEvent(request.customer_id)
            await self._journal.append(event)
        return CloseCustomerAccountResponse(customer_id=request.customer_id)
