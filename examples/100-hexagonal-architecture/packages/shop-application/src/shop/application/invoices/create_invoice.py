"""Create an invoice from a durable order integration message."""

from dataclasses import dataclass

from pymediate import Request, RequestHandler

from shop.domain.entities.invoices import Invoice
from shop.domain.errors.invoices import InvoiceNotFoundError
from shop.domain.events.invoices import InvoiceCreatedEvent
from shop.ports.audit import DomainEventJournal
from shop.ports.invoices.create_invoice import (
    CreateInvoiceDbGateway,
    CreateInvoiceRenderer,
    CreateInvoiceStorage,
)
from shop.ports.unit_of_work import UnitOfWork


@dataclass(frozen=True)
class CreateInvoiceResponse:
    """Expose the created invoice without leaking its domain representation."""

    invoice_id: int
    order_id: int
    document_url: str


@dataclass(frozen=True)
class CreateInvoiceRequest(Request[CreateInvoiceResponse]):
    """Create one idempotent invoice for a placed order."""

    order_id: int
    customer_id: int
    total_pence: int
    idempotency_key: str


class CreateInvoiceHandler(RequestHandler[CreateInvoiceRequest]):
    """Render, store, and persist an invoice once per order."""

    def __init__(
        self,
        unit: UnitOfWork,
        database: CreateInvoiceDbGateway,
        renderer: CreateInvoiceRenderer,
        storage: CreateInvoiceStorage,
        journal: DomainEventJournal,
    ) -> None:
        self._unit = unit
        self._database = database
        self._renderer = renderer
        self._storage = storage
        self._journal = journal

    async def __call__(self, request: CreateInvoiceRequest) -> CreateInvoiceResponse:
        try:
            existing = await self._database.get_invoice_for_order(request.order_id)
        except InvoiceNotFoundError:
            existing = None
        if existing is not None:
            return CreateInvoiceResponse(
                existing.invoice_id, existing.order_id, existing.document_url
            )

        content = await self._renderer.render_invoice(
            request.order_id, request.customer_id, request.total_pence
        )
        url = await self._storage.write_invoice(
            request.order_id, content, idempotency_key=request.idempotency_key
        )
        async with self._unit:
            invoice = Invoice(
                await self._database.next_invoice_identity(),
                request.order_id,
                request.customer_id,
                request.total_pence,
                url,
            )
            await self._database.insert_invoice(invoice)
            event = InvoiceCreatedEvent(
                invoice.invoice_id,
                invoice.order_id,
                invoice.customer_id,
                invoice.total_pence,
                invoice.document_url,
            )
            await self._journal.append(event)
        return CreateInvoiceResponse(invoice.invoice_id, invoice.order_id, invoice.document_url)
