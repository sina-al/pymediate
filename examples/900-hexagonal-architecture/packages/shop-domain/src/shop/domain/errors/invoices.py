"""Business failures owned by the invoices feature module."""

from shop.domain.errors import DomainError


class InvoiceNotFoundError(DomainError):
    code = "invoice-not-found"
    title = "Invoice not found"

    def __init__(self, order_id: int) -> None:
        super().__init__(f"No invoice exists for order {order_id}.", order_id=order_id)


class InvalidInvoiceSnapshotError(DomainError, ValueError):
    code = "invalid-invoice-snapshot"
    title = "Invalid invoice"

    def __init__(self, field: str, value: object) -> None:
        super().__init__(
            f"Invoice field '{field}' is invalid.",
            field=field,
            value=value,
        )
