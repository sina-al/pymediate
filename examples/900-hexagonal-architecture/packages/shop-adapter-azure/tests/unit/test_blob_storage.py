"""Test Azure Blob Storage translation without an application or broker."""

from collections.abc import AsyncIterator
from typing import BinaryIO

import pytest

from shop.adapters.azure import AzureBlobStorage


async def rows() -> AsyncIterator[str]:
    yield "header\n"
    yield "row\n"


class AzureBlob:
    uploaded: bytes = b""

    async def upload_blob(self, source: bytes | BinaryIO, *, overwrite: bool) -> None:
        self.uploaded = source if isinstance(source, bytes) else source.read()


class AzureBlobService:
    def __init__(self) -> None:
        self.blob = AzureBlob()

    def get_blob_client(self, *, container: str, blob: str) -> AzureBlob:
        return self.blob

    async def close(self) -> None:
        pass


async def test_azure_storage_uploads_an_incremental_export(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    client = AzureBlobService()
    monkeypatch.setattr(
        "azure.storage.blob.aio.BlobServiceClient.from_connection_string",
        lambda connection_string: client,
    )
    storage = AzureBlobStorage("exports", "UseDevelopmentStorage=true")

    # Act
    url = await storage.write(7, "csv", rows())

    # Assert
    assert url == "azblob://exports/exports/7.csv"
    assert client.blob.uploaded == b"header\nrow\n"
    await storage.close()
