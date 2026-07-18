"""Invoice entities owned by the invoicing feature module."""

from dataclasses import dataclass

from shop.domain.errors import InvalidIdentifierError
from shop.domain.errors.invoices import InvalidInvoiceSnapshotError
from shop.domain.errors.orders import InvalidPriceError


@dataclass(frozen=True)
class Invoice:
    """A rendered invoice associated with one order."""

    invoice_id: int
    order_id: int
    customer_id: int
    total_pence: int
    document_url: str

    def __post_init__(self) -> None:
        for kind, value in (
            ("invoice_id", self.invoice_id),
            ("order_id", self.order_id),
            ("customer_id", self.customer_id),
        ):
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise InvalidIdentifierError(kind, value)
        if (
            not isinstance(self.total_pence, int)
            or isinstance(self.total_pence, bool)
            or self.total_pence < 1
        ):
            raise InvalidPriceError(self.total_pence)
        if not isinstance(self.document_url, str) or not self.document_url.strip():
            raise InvalidInvoiceSnapshotError("document_url", self.document_url)
