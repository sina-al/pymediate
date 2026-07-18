"""Test S3 storage translation without an application or broker."""

from collections.abc import AsyncIterator
from typing import BinaryIO

import pytest

from shop.adapters.aws import S3Storage


async def rows() -> AsyncIterator[str]:
    yield "header\n"
    yield "row\n"


class S3Client:
    uploaded: bytes = b""

    def upload_fileobj(self, source: BinaryIO, bucket: str, key: str) -> None:
        self.uploaded = source.read()

    def put_object(self, *, Bucket: str, Key: str, Body: bytes) -> None:
        self.uploaded = Body


async def test_s3_storage_uploads_an_incremental_export(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    client = S3Client()
    monkeypatch.setattr("boto3.client", lambda *args, **kwargs: client)
    storage = S3Storage("exports", "http://minio:9000")

    # Act
    url = await storage.write(7, "csv", rows())

    # Assert
    assert url == "s3://exports/exports/7.csv"
    assert client.uploaded == b"header\nrow\n"
