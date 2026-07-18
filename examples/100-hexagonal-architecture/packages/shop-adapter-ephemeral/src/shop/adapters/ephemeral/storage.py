"""Local object-storage adapter."""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from shop.ports.invoices.create_invoice import CreateInvoiceStorage
from shop.ports.orders.export_orders import ExportOrdersStorage
from shop.ports.statements.create_monthly_statement import MonthlyStatementStorage


@dataclass
class EphemeralStorage(ExportOrdersStorage, CreateInvoiceStorage, MonthlyStatementStorage):
    """Keep generated objects in memory when no object store is configured."""

    exports: dict[int, str] = field(default_factory=dict)
    documents: dict[str, bytes] = field(default_factory=dict)
    idempotency_keys: set[str] = field(default_factory=set)

    async def write(
        self,
        customer_id: int,
        format: str,
        rows: AsyncIterator[str],
        idempotency_key: str | None = None,
    ) -> str:
        url = f"memory://exports/{customer_id}.{format}"
        if idempotency_key is not None and idempotency_key in self.idempotency_keys:
            return url
        content = "".join([row async for row in rows])
        self.exports[customer_id] = content
        if idempotency_key is not None:
            self.idempotency_keys.add(idempotency_key)
        return url

    async def write_invoice(
        self, order_id: int, content: bytes, idempotency_key: str | None = None
    ) -> str:
        key = f"invoices/{idempotency_key or order_id}.pdf"
        if idempotency_key is not None and idempotency_key in self.idempotency_keys:
            return f"memory://{key}"
        if idempotency_key is not None:
            self.idempotency_keys.add(idempotency_key)
        self.documents[key] = content
        return f"memory://{key}"

    async def write_statement(self, customer_id: int, year: int, month: int, content: bytes) -> str:
        key = f"statements/{customer_id}/{year:04d}-{month:02d}.pdf"
        self.documents[key] = content
        return f"memory://{key}"
