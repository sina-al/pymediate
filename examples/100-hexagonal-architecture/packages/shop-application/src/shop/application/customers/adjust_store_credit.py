"""Adjust a customer's store-credit balance through an explicit transaction."""

from dataclasses import dataclass

from pymediate import Request, RequestHandler

from shop.domain.entities.customers import CustomerAccount
from shop.domain.events.customers import StoreCreditAdjustedEvent
from shop.ports.audit import DomainEventJournal
from shop.ports.customers.adjust_store_credit import AdjustStoreCreditDbGateway
from shop.ports.unit_of_work import UnitOfWork


@dataclass(frozen=True)
class AdjustStoreCreditResponse:
    """Return the customer's resulting public balance."""

    customer_id: int
    store_credit_pence: int


@dataclass(frozen=True)
class AdjustStoreCreditRequest(Request[AdjustStoreCreditResponse]):
    """Credit a positive amount to one customer account."""

    customer_id: int
    amount_pence: int


class AdjustStoreCreditHandler(RequestHandler[AdjustStoreCreditRequest]):
    """Apply the customer aggregate rule and persist the new immutable state."""

    def __init__(
        self,
        unit: UnitOfWork,
        database: AdjustStoreCreditDbGateway,
        journal: DomainEventJournal,
    ) -> None:
        self._unit = unit
        self._database = database
        self._journal = journal

    async def __call__(self, request: AdjustStoreCreditRequest) -> AdjustStoreCreditResponse:
        async with self._unit:
            customer: CustomerAccount = await self._database.get_customer(request.customer_id)
            credited = customer.add_store_credit(request.amount_pence)
            await self._database.replace_customer(credited)
            event = StoreCreditAdjustedEvent(
                credited.customer_id, request.amount_pence, credited.store_credit_pence
            )
            await self._journal.append(event)
        return AdjustStoreCreditResponse(credited.customer_id, credited.store_credit_pence)
