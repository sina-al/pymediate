"""Test invoice retrieval by calling the handler directly."""

import pytest

from shop.application.invoices.get_invoice import GetInvoiceHandler, GetInvoiceRequest
from shop.domain.entities.invoices import Invoice
from shop.domain.errors.invoices import InvoiceNotFoundError
from shop.ports.invoices.get_invoice import GetInvoiceDbGateway

from ..support import autospec


async def test_get_invoice_maps_the_domain_entity_to_an_explicit_response() -> None:
    # Arrange
    database = autospec(GetInvoiceDbGateway)
    database.get_invoice_for_order.return_value = Invoice(8, 1, 7, 3_000, "s3://invoice.pdf")
    handle = GetInvoiceHandler(database)

    # Act
    result = await handle(GetInvoiceRequest(1))

    # Assert
    assert result.invoice_id == 8
    assert result.order_id == 1
    assert result.customer_id == 7
    assert result.total_pence == 3_000
    assert result.document_url == "s3://invoice.pdf"
    assert not hasattr(result, "customer")
    database.get_invoice_for_order.assert_awaited_once_with(1)


async def test_get_invoice_propagates_the_structured_not_found_error() -> None:
    # Arrange
    database = autospec(GetInvoiceDbGateway)
    database.get_invoice_for_order.side_effect = InvoiceNotFoundError(1)
    handle = GetInvoiceHandler(database)

    # Act
    with pytest.raises(InvoiceNotFoundError):
        await handle(GetInvoiceRequest(1))

    # Assert
    database.get_invoice_for_order.assert_awaited_once_with(1)
