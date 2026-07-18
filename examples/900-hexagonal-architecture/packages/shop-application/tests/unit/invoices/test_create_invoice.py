"""Test invoice creation by calling the handler directly."""

from shop.application.invoices.create_invoice import (
    CreateInvoiceHandler,
    CreateInvoiceRequest,
)
from shop.domain.entities.invoices import Invoice
from shop.domain.errors.invoices import InvoiceNotFoundError
from shop.domain.events.invoices import InvoiceCreatedEvent
from shop.ports.audit import DomainEventJournal
from shop.ports.invoices.create_invoice import (
    CreateInvoiceDbGateway,
    CreateInvoiceRenderer,
    CreateInvoiceStorage,
)

from ..support import autospec, autospec_unit


async def test_create_invoice_renders_stores_and_persists() -> None:
    # Arrange
    unit = autospec_unit()
    database = autospec(CreateInvoiceDbGateway)
    renderer = autospec(CreateInvoiceRenderer)
    storage = autospec(CreateInvoiceStorage)
    journal = autospec(DomainEventJournal)
    database.get_invoice_for_order.side_effect = InvoiceNotFoundError(1)
    database.next_invoice_identity.return_value = 42
    renderer.render_invoice.return_value = b"pdf"
    storage.write_invoice.return_value = "s3://invoices/message-1.pdf"
    handle = CreateInvoiceHandler(unit, database, renderer, storage, journal)

    # Act
    result = await handle(CreateInvoiceRequest(1, 7, 3_000, "message-1"))

    # Assert
    assert result.invoice_id == 42
    assert result.order_id == 1
    assert result.document_url == "s3://invoices/message-1.pdf"
    renderer.render_invoice.assert_awaited_once_with(1, 7, 3_000)
    storage.write_invoice.assert_awaited_once_with(1, b"pdf", idempotency_key="message-1")
    invoice = Invoice(42, 1, 7, 3_000, "s3://invoices/message-1.pdf")
    database.insert_invoice.assert_awaited_once_with(invoice)
    journal.append.assert_awaited_once_with(
        InvoiceCreatedEvent(42, 1, 7, 3_000, "s3://invoices/message-1.pdf")
    )
    unit.__aexit__.assert_awaited_once_with(None, None, None)


async def test_existing_invoice_is_returned_without_repeating_effects() -> None:
    # Arrange
    unit = autospec_unit()
    database = autospec(CreateInvoiceDbGateway)
    renderer = autospec(CreateInvoiceRenderer)
    storage = autospec(CreateInvoiceStorage)
    journal = autospec(DomainEventJournal)
    database.get_invoice_for_order.return_value = Invoice(8, 1, 7, 3_000, "s3://existing.pdf")
    handle = CreateInvoiceHandler(unit, database, renderer, storage, journal)

    # Act
    result = await handle(CreateInvoiceRequest(1, 7, 3_000, "duplicate"))

    # Assert
    assert result.invoice_id == 8
    assert result.document_url == "s3://existing.pdf"
    renderer.render_invoice.assert_not_awaited()
    storage.write_invoice.assert_not_awaited()
    database.next_invoice_identity.assert_not_awaited()
    database.insert_invoice.assert_not_awaited()
    journal.append.assert_not_awaited()
    unit.__aenter__.assert_not_awaited()
