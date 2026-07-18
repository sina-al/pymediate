"""Test durable export requests by calling the handler directly."""

import pytest

from shop.application.orders.request_order_export import (
    RequestOrderExportHandler,
    RequestOrderExportRequest,
)
from shop.domain.errors.orders import UnsupportedExportFormatError
from shop.ports.audit import DomainEventJournal
from shop.ports.orders.request_order_export import RequestOrderExportDbGateway

from ..support import autospec, autospec_unit


@pytest.mark.parametrize("format", ["csv", "jsonl"])
async def test_request_export_records_versioned_serializable_intent(format: str) -> None:
    # Arrange
    unit = autospec_unit()
    database = autospec(RequestOrderExportDbGateway)
    journal = autospec(DomainEventJournal)
    handle = RequestOrderExportHandler(unit, database, journal)

    # Act
    result = await handle(RequestOrderExportRequest(7, format))

    # Assert
    message = database.insert_outbox_message.await_args.args[0]
    assert result.job_id == message.message_id
    assert result.customer_id == 7
    assert message.message.event_type == "shop.orders.order-export-requested"
    assert message.message.schema_version == 1
    assert message.message.payload == {"customer_id": 7, "format": format}
    unit.__aexit__.assert_awaited_once_with(None, None, None)


async def test_unknown_format_is_rejected_before_message_or_transaction() -> None:
    # Arrange
    unit = autospec_unit()
    database = autospec(RequestOrderExportDbGateway)
    journal = autospec(DomainEventJournal)
    handle = RequestOrderExportHandler(unit, database, journal)

    # Act
    with pytest.raises(UnsupportedExportFormatError):
        await handle(RequestOrderExportRequest(7, "xml"))

    # Assert
    unit.__aenter__.assert_not_awaited()
    database.insert_outbox_message.assert_not_awaited()


async def test_outbox_failure_leaves_transaction_to_roll_back() -> None:
    # Arrange
    unit = autospec_unit()
    database = autospec(RequestOrderExportDbGateway)
    journal = autospec(DomainEventJournal)
    database.insert_outbox_message.side_effect = RuntimeError("outbox unavailable")
    handle = RequestOrderExportHandler(unit, database, journal)

    # Act
    with pytest.raises(RuntimeError, match="outbox unavailable"):
        await handle(RequestOrderExportRequest(7))

    # Assert
    assert unit.__aexit__.await_args.args[0] is RuntimeError
