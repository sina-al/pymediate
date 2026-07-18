"""Retrieve an invoice without exposing its persistence adapter."""

from dataclasses import dataclass

from pymediate import Request, RequestHandler

from shop.domain.entities.invoices import Invoice
from shop.ports.invoices.get_invoice import GetInvoiceDbGateway


@dataclass(frozen=True)
class GetInvoiceResponse:
    """Public invoice fields selected for application callers."""

    invoice_id: int
    order_id: int
    customer_id: int
    total_pence: int
    document_url: str

    @classmethod
    def from_domain(cls, invoice: Invoice) -> "GetInvoiceResponse":
        """Select the fields allowed to cross the application boundary."""
        return cls(
            invoice.invoice_id,
            invoice.order_id,
            invoice.customer_id,
            invoice.total_pence,
            invoice.document_url,
        )


@dataclass(frozen=True)
class GetInvoiceRequest(Request[GetInvoiceResponse]):
    """Request the invoice generated for one order."""

    order_id: int


class GetInvoiceHandler(RequestHandler[GetInvoiceRequest]):
    """Read one invoice through an invoice-owned port."""

    def __init__(self, database: GetInvoiceDbGateway) -> None:
        self._database = database

    async def __call__(self, request: GetInvoiceRequest) -> GetInvoiceResponse:
        invoice = await self._database.get_invoice_for_order(request.order_id)
        return GetInvoiceResponse.from_domain(invoice)
