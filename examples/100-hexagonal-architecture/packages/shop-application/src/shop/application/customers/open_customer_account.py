"""Open a customer account through an explicit transaction."""

from dataclasses import dataclass

from pymediate import Request, RequestHandler

from shop.domain.entities.customers import CustomerAccount
from shop.domain.events.customers import CustomerAccountOpenedEvent
from shop.ports.audit import DomainEventJournal
from shop.ports.customers.open_customer_account import OpenCustomerAccountDbGateway
from shop.ports.unit_of_work import UnitOfWork


@dataclass(frozen=True)
class OpenCustomerAccountResponse:
    """Return the public state of the newly opened account."""

    customer_id: int
    store_credit_pence: int


@dataclass(frozen=True)
class OpenCustomerAccountRequest(Request[OpenCustomerAccountResponse]):
    """Open one customer account with a zero store-credit balance."""

    customer_id: int


class OpenCustomerAccountHandler(RequestHandler[OpenCustomerAccountRequest]):
    """Create the immutable account and record its business fact atomically."""

    def __init__(
        self,
        unit: UnitOfWork,
        database: OpenCustomerAccountDbGateway,
        journal: DomainEventJournal,
    ) -> None:
        self._unit = unit
        self._database = database
        self._journal = journal

    async def __call__(self, request: OpenCustomerAccountRequest) -> OpenCustomerAccountResponse:
        customer = CustomerAccount.open(request.customer_id)
        async with self._unit:
            await self._database.insert_customer(customer)
            await self._journal.append(CustomerAccountOpenedEvent(customer.customer_id))
        return OpenCustomerAccountResponse(customer.customer_id, customer.store_credit_pence)
