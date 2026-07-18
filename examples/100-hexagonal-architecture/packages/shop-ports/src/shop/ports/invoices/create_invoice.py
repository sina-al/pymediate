"""Narrow ports required to create an invoice after an order is placed."""

from typing import Protocol, runtime_checkable

from shop.domain.entities.invoices import Invoice


@runtime_checkable
class CreateInvoiceDbGateway(Protocol):
    """Allocate and persist one invoice."""

    async def next_invoice_identity(self) -> int: ...
    async def insert_invoice(self, invoice: Invoice) -> None: ...
    async def get_invoice_for_order(self, order_id: int) -> Invoice: ...


@runtime_checkable
class CreateInvoiceRenderer(Protocol):
    """Render invoice content without choosing its storage vendor."""

    async def render_invoice(self, order_id: int, customer_id: int, total_pence: int) -> bytes: ...


@runtime_checkable
class CreateInvoiceStorage(Protocol):
    """Persist a rendered invoice and return its location."""

    async def write_invoice(
        self, order_id: int, content: bytes, idempotency_key: str | None = None
    ) -> str: ...
