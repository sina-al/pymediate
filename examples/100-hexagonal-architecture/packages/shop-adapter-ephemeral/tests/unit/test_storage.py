"""Exercise local object storage, including retry-safe idempotency."""

from collections.abc import AsyncIterator

import pytest

from shop.adapters.ephemeral import EphemeralStorage


async def rows(*values: str) -> AsyncIterator[str]:
    for value in values:
        yield value


async def failing_rows() -> AsyncIterator[str]:
    yield "partial"
    raise RuntimeError("stream failed")


async def test_export_write_suppresses_a_duplicate_idempotency_key() -> None:
    # Arrange
    storage = EphemeralStorage()

    # Act
    first_url = await storage.write(7, "csv", rows("header\n", "first\n"), "message-1")
    duplicate_url = await storage.write(7, "csv", rows("replacement\n"), "message-1")

    # Assert
    assert first_url == duplicate_url == "memory://exports/7.csv"
    assert storage.exports == {7: "header\nfirst\n"}
    assert storage.idempotency_keys == {"message-1"}


async def test_failed_export_stream_does_not_poison_an_idempotent_retry() -> None:
    # Arrange
    storage = EphemeralStorage()

    # Act
    with pytest.raises(RuntimeError, match="stream failed"):
        await storage.write(7, "jsonl", failing_rows(), "message-1")
    retry_url = await storage.write(7, "jsonl", rows('{"order_id": 1}\n'), "message-1")

    # Assert
    assert retry_url == "memory://exports/7.jsonl"
    assert storage.exports == {7: '{"order_id": 1}\n'}
    assert storage.idempotency_keys == {"message-1"}


async def test_invoice_write_keeps_the_first_effect_for_a_message() -> None:
    # Arrange
    storage = EphemeralStorage()

    # Act
    first_url = await storage.write_invoice(42, b"first invoice", "message-1")
    duplicate_url = await storage.write_invoice(42, b"replacement", "message-1")

    # Assert
    assert first_url == duplicate_url == "memory://invoices/message-1.pdf"
    assert storage.documents == {"invoices/message-1.pdf": b"first invoice"}
    assert storage.idempotency_keys == {"message-1"}


async def test_non_idempotent_documents_use_stable_business_keys() -> None:
    # Arrange
    storage = EphemeralStorage()

    # Act
    invoice_url = await storage.write_invoice(42, b"invoice")
    statement_url = await storage.write_statement(7, 2026, 7, b"statement")

    # Assert
    assert invoice_url == "memory://invoices/42.pdf"
    assert statement_url == "memory://statements/7/2026-07.pdf"
    assert storage.documents == {
        "invoices/42.pdf": b"invoice",
        "statements/7/2026-07.pdf": b"statement",
    }
    assert storage.idempotency_keys == set()
