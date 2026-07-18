"""Narrow outbound ports required only by the export-orders use case."""

from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable

from shop.domain.entities.orders import Order


@runtime_checkable
class ExportOrdersDbGateway(Protocol):
    """Stream a customer's orders without exposing database machinery."""

    def stream_orders(self, customer_id: int) -> AsyncIterator[Order]: ...


@runtime_checkable
class ExportOrdersStorage(Protocol):
    """Store one streamed export and return its download location."""

    async def write(
        self,
        customer_id: int,
        format: str,
        rows: AsyncIterator[str],
        idempotency_key: str | None = None,
    ) -> str: ...


@runtime_checkable
class ExportOrdersMailer(Protocol):
    """Tell a customer where an idempotently generated export is available."""

    async def send_export_ready(
        self,
        recipient: str,
        download_url: str,
        idempotency_key: str | None = None,
    ) -> None: ...
