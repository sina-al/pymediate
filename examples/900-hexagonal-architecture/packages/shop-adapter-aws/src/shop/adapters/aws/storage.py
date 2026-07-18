"""Amazon S3 document-storage adapter."""

import asyncio
from collections.abc import AsyncIterator
from tempfile import SpooledTemporaryFile
from types import TracebackType
from typing import Any, Self

import boto3

from shop.ports.invoices.create_invoice import CreateInvoiceStorage
from shop.ports.orders.export_orders import ExportOrdersStorage
from shop.ports.statements.create_monthly_statement import MonthlyStatementStorage


class S3Storage(ExportOrdersStorage, CreateInvoiceStorage, MonthlyStatementStorage):
    """Store streamed exports and rendered documents in S3.

    ``endpoint_url`` makes the same adapter usable with S3-compatible local services such
    as MinIO without leaking emulator concerns into the application.
    """

    def __init__(self, bucket: str, endpoint_url: str | None = None) -> None:
        self._bucket = bucket
        self._client: Any = boto3.client("s3", endpoint_url=endpoint_url)

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await asyncio.to_thread(self._client.close)

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
            await asyncio.to_thread(self._client.upload_fileobj, output, self._bucket, key)
        return f"s3://{self._bucket}/{key}"

    async def write_invoice(
        self, order_id: int, content: bytes, idempotency_key: str | None = None
    ) -> str:
        return await self._write_bytes(f"invoices/{idempotency_key or order_id}.pdf", content)

    async def write_statement(self, customer_id: int, year: int, month: int, content: bytes) -> str:
        return await self._write_bytes(
            f"statements/{customer_id}/{year:04d}-{month:02d}.pdf", content
        )

    async def _write_bytes(self, key: str, content: bytes) -> str:
        await asyncio.to_thread(
            self._client.put_object,
            Bucket=self._bucket,
            Key=key,
            Body=content,
            ContentType="application/pdf",
        )
        return f"s3://{self._bucket}/{key}"
