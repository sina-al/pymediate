"""Azure Blob Storage document-storage adapter."""

from collections.abc import AsyncIterator
from tempfile import SpooledTemporaryFile
from types import TracebackType
from typing import Any, Self

from azure.storage.blob import ContentSettings
from azure.storage.blob.aio import BlobServiceClient
from shop.ports.invoices.create_invoice import CreateInvoiceStorage
from shop.ports.orders.export_orders import ExportOrdersStorage
from shop.ports.statements.create_monthly_statement import MonthlyStatementStorage


class AzureBlobStorage(ExportOrdersStorage, CreateInvoiceStorage, MonthlyStatementStorage):
    """Store documents in Azure Blob Storage or its Azurite emulator."""

    def __init__(self, container: str, connection_string: str) -> None:
        self._container = container
        self._client = BlobServiceClient.from_connection_string(connection_string)

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.close()

    async def write(
        self,
        customer_id: int,
        format: str,
        rows: AsyncIterator[str],
        idempotency_key: str | None = None,
    ) -> str:
        key = f"exports/{idempotency_key or customer_id}.{format}"
        with SpooledTemporaryFile(max_size=1_000_000) as output:
            async for row in rows:
                output.write(row.encode())
            output.seek(0)
            await self._upload(key, output)
        return self._uri(key)

    async def write_invoice(
        self, order_id: int, content: bytes, idempotency_key: str | None = None
    ) -> str:
        key = f"invoices/{idempotency_key or order_id}.pdf"
        await self._upload(key, content, content_type="application/pdf")
        return self._uri(key)

    async def write_statement(self, customer_id: int, year: int, month: int, content: bytes) -> str:
        key = f"statements/{customer_id}/{year:04d}-{month:02d}.pdf"
        await self._upload(key, content, content_type="application/pdf")
        return self._uri(key)

    async def _upload(self, key: str, content: Any, content_type: str | None = None) -> None:
        blob = self._client.get_blob_client(container=self._container, blob=key)
        if content_type is None:
            await blob.upload_blob(content, overwrite=True)
        else:
            await blob.upload_blob(
                content,
                overwrite=True,
                content_settings=ContentSettings(content_type=content_type),
            )

    def _uri(self, key: str) -> str:
        return f"azblob://{self._container}/{key}"

    async def close(self) -> None:
        """Close the underlying asynchronous storage client."""
        await self._client.close()
