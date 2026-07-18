"""Test streamed order export by calling the handler directly."""

from collections.abc import AsyncIterator
from datetime import date

import pytest

from shop.application.orders.export_orders import ExportOrdersHandler, ExportOrdersRequest
from shop.domain.entities.orders import Order, OrderLine
from shop.domain.errors.orders import UnsupportedExportFormatError
from shop.ports.orders.export_orders import (
    ExportOrdersDbGateway,
    ExportOrdersMailer,
    ExportOrdersStorage,
)

from ..support import autospec


def order(order_id: int) -> Order:
    return Order.place(order_id, 7, (OrderLine("book", 1, 1_500),), date(2026, 7, 13))


def stream(*orders: Order) -> AsyncIterator[Order]:
    async def values() -> AsyncIterator[Order]:
        for value in orders:
            yield value

    return values()


async def stored_rows(rows: AsyncIterator[str]) -> str:
    return "".join([row async for row in rows])


@pytest.mark.parametrize(
    ("format", "expected"),
    [
        ("csv", "order_id,total_pence,status\n1,1500,placed\n2,1500,placed\n"),
        (
            "jsonl",
            '{"order_id":1,"total_pence":1500,"status":"placed"}\n'
            '{"order_id":2,"total_pence":1500,"status":"placed"}\n',
        ),
    ],
)
async def test_export_stores_rows_then_sends_the_download_location(
    format: str, expected: str
) -> None:
    # Arrange
    database = autospec(ExportOrdersDbGateway)
    storage = autospec(ExportOrdersStorage)
    mailer = autospec(ExportOrdersMailer)
    database.stream_orders.return_value = stream(order(1), order(2))
    writes: list[tuple[int, str, str, str | None]] = []

    async def write(
        customer_id: int,
        selected_format: str,
        rows: AsyncIterator[str],
        idempotency_key: str | None = None,
    ) -> str:
        writes.append((customer_id, selected_format, await stored_rows(rows), idempotency_key))
        return f"memory://7.{format}"

    storage.write.side_effect = write
    handle = ExportOrdersHandler(database, storage, mailer)

    # Act
    result = await handle(ExportOrdersRequest(7, format, "message-1"))

    # Assert
    assert result.url == f"memory://7.{format}"
    assert result.rows == 2
    assert writes == [(7, format, expected, "message-1")]
    database.stream_orders.assert_called_once_with(7)
    storage.write.assert_awaited_once()
    mailer.send_export_ready.assert_awaited_once_with(
        "customer-7@example.com",
        f"memory://7.{format}",
        idempotency_key="message-1",
    )


async def test_empty_export_still_contains_csv_header() -> None:
    # Arrange
    database = autospec(ExportOrdersDbGateway)
    storage = autospec(ExportOrdersStorage)
    mailer = autospec(ExportOrdersMailer)
    database.stream_orders.return_value = stream()
    writes: list[str] = []

    async def write(
        customer_id: int,
        format: str,
        rows: AsyncIterator[str],
        idempotency_key: str | None = None,
    ) -> str:
        writes.append(await stored_rows(rows))
        return "memory://empty.csv"

    storage.write.side_effect = write
    handle = ExportOrdersHandler(database, storage, mailer)

    # Act
    result = await handle(ExportOrdersRequest(7))

    # Assert
    assert result.rows == 0
    assert writes == ["order_id,total_pence,status\n"]
    mailer.send_export_ready.assert_awaited_once_with(
        "customer-7@example.com", "memory://empty.csv", idempotency_key=None
    )


async def test_unknown_format_fails_before_database_or_storage() -> None:
    # Arrange
    database = autospec(ExportOrdersDbGateway)
    storage = autospec(ExportOrdersStorage)
    mailer = autospec(ExportOrdersMailer)
    handle = ExportOrdersHandler(database, storage, mailer)

    # Act
    with pytest.raises(UnsupportedExportFormatError):
        await handle(ExportOrdersRequest(7, "xml"))

    # Assert
    database.stream_orders.assert_not_called()
    storage.write.assert_not_awaited()
    mailer.send_export_ready.assert_not_awaited()


async def test_storage_failure_does_not_announce_an_unavailable_export() -> None:
    # Arrange
    database = autospec(ExportOrdersDbGateway)
    storage = autospec(ExportOrdersStorage)
    storage.write.side_effect = RuntimeError("storage unavailable")
    mailer = autospec(ExportOrdersMailer)
    database.stream_orders.return_value = stream(order(1))
    handle = ExportOrdersHandler(database, storage, mailer)

    # Act
    with pytest.raises(RuntimeError, match="storage unavailable"):
        await handle(ExportOrdersRequest(7, "csv", "message-1"))

    # Assert
    mailer.send_export_ready.assert_not_awaited()


async def test_mail_failure_is_propagated_after_storage_succeeds() -> None:
    # Arrange
    database = autospec(ExportOrdersDbGateway)
    storage = autospec(ExportOrdersStorage)
    storage.write.return_value = "memory://7.csv"
    mailer = autospec(ExportOrdersMailer)
    mailer.send_export_ready.side_effect = RuntimeError("mail unavailable")
    database.stream_orders.return_value = stream(order(1))
    handle = ExportOrdersHandler(database, storage, mailer)

    # Act
    with pytest.raises(RuntimeError, match="mail unavailable"):
        await handle(ExportOrdersRequest(7, "csv", "message-1"))

    # Assert
    storage.write.assert_awaited_once()
    mailer.send_export_ready.assert_awaited_once_with(
        "customer-7@example.com", "memory://7.csv", idempotency_key="message-1"
    )
