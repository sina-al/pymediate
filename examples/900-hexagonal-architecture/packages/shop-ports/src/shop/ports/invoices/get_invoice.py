"""Read port for retrieving an invoice by order."""

from typing import Protocol, runtime_checkable

from shop.domain.entities.invoices import Invoice


@runtime_checkable
class GetInvoiceDbGateway(Protocol):
    """Return the invoice belonging to one order."""

    async def get_invoice_for_order(self, order_id: int) -> Invoice: ...
