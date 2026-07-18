"""Exercise invoice queries through the assembled mediator."""

import pytest

from shop.application.invoices.create_invoice import CreateInvoiceRequest
from shop.application.invoices.get_invoice import GetInvoiceRequest
from shop.domain.entities.invoices import Invoice
from shop.domain.errors.invoices import InvoiceNotFoundError
from shop.domain.events.base import AggregateType

from .support import ApplicationHarness


async def test_create_invoice_is_idempotent_through_the_mediator(
    application: ApplicationHarness,
) -> None:
    # Arrange
    request = CreateInvoiceRequest(42, 7, 1_500, "invoice-message")

    # Act
    created = await application.mediator.send(request)
    repeated = await application.mediator.send(request)

    # Assert
    assert repeated == created
    assert created.order_id == 42
    assert created.document_url == "memory://invoices/invoice-message.pdf"
    assert list(application.storage.documents) == ["invoices/invoice-message.pdf"]
    events = await application.events(AggregateType.INVOICE, created.invoice_id)
    assert len(events) == 1
    assert events[0].event_type == "invoices.invoice-created"


async def test_get_invoice_returns_a_persisted_invoice(
    application: ApplicationHarness,
) -> None:
    # Arrange
    await application.database.insert_invoice(Invoice(1, 42, 7, 1_500, "memory://invoices/42.pdf"))

    # Act
    invoice = await application.mediator.send(GetInvoiceRequest(42))

    # Assert
    assert invoice.invoice_id == 1
    assert invoice.order_id == 42
    assert invoice.total_pence == 1_500
    assert invoice.document_url == "memory://invoices/42.pdf"


async def test_get_invoice_reports_missing_invoice(
    application: ApplicationHarness,
) -> None:
    # Arrange
    missing_order_id = 999

    # Act
    with pytest.raises(InvoiceNotFoundError) as raised:
        await application.mediator.send(GetInvoiceRequest(missing_order_id))

    # Assert
    assert raised.value.context == {"order_id": missing_order_id}
