"""Exercise every orders request through the assembled mediator graph."""

import pytest

from shop.application.orders.cancel_order import CancelOrderRequest
from shop.application.orders.create_order import CreateOrderRequest
from shop.application.orders.export_orders import ExportOrdersRequest
from shop.application.orders.get_order_history import GetOrderHistoryRequest
from shop.application.orders.refund_order import RefundOrderRequest
from shop.application.orders.request_order_export import RequestOrderExportRequest
from shop.application.orders.send_order_confirmation import SendOrderConfirmationRequest
from shop.domain.entities.orders import OrderItem, OrderStatus
from shop.domain.errors.orders import (
    EmptyOrderError,
    ExcessiveRefundError,
    InvalidOrderStateError,
    ProductNotFoundError,
    UnsupportedExportFormatError,
)
from shop.domain.events.base import AggregateType

from .support import ApplicationHarness


async def test_create_order_persists_charges_and_domain_events(
    application: ApplicationHarness,
) -> None:
    # Arrange
    request = CreateOrderRequest(7, (OrderItem("book", 2), OrderItem("mug", 1)))

    # Act
    result = await application.mediator.send(request)

    # Assert
    assert result.total_pence == 3_900
    orders = await application.database.orders()
    assert orders[0].order_id == result.order_id
    assert orders[0].total_pence == result.total_pence
    assert not hasattr(result, "lines")
    assert application.payments.charges == [(1, 3_900)]
    events = await application.events(AggregateType.ORDER, 1)
    event_names = [event.event_type for event in events]
    assert event_names == [
        "orders.order-placed",
    ]
    messages = await application.database.claim_outbox_messages(10, 120)
    assert {claim.message.message.event_type for claim in messages} == {
        "shop.orders.order-confirmation-requested",
        "shop.invoices.invoice-requested",
    }
    assert events[0].event_id not in {claim.message_id for claim in messages}
    assert application.mailer.messages == []


@pytest.mark.parametrize(
    ("command", "error_type"),
    [
        (CreateOrderRequest(7, ()), EmptyOrderError),
        (CreateOrderRequest(7, (OrderItem("unknown", 1),)), ProductNotFoundError),
    ],
)
async def test_create_order_failure_has_no_committed_side_effects(
    application: ApplicationHarness,
    command: CreateOrderRequest,
    error_type: type[Exception],
) -> None:
    # Arrange
    request = command

    # Act
    with pytest.raises(error_type):
        await application.mediator.send(request)

    # Assert
    assert await application.database.orders() == []
    assert application.payments.charges == []
    assert application.mailer.messages == []
    assert await application.events(AggregateType.ORDER, 1) == ()


async def test_cancel_order_updates_state_and_compensates_external_work(
    application: ApplicationHarness,
) -> None:
    # Arrange
    placed = await application.seed_order()

    # Act
    cancelled = await application.mediator.send(CancelOrderRequest(placed.order_id))

    # Assert
    assert cancelled.status == OrderStatus.CANCELLED.value
    assert (await application.database.orders())[0].status is OrderStatus.CANCELLED
    assert application.inventory.releases == [(OrderItem("book", 2),)]
    assert application.payments.voids == [(1, 3_000)]
    assert application.mailer.messages == [("customer-7@example.com", "Order 1 cancelled")]
    assert (await application.events(AggregateType.ORDER, 1))[
        -1
    ].event_type == "orders.order-cancelled"


async def test_cancel_order_rejects_non_placed_state_without_compensation(
    application: ApplicationHarness,
) -> None:
    # Arrange
    partially_refunded = (await application.seed_order()).refund(500)
    await application.database.replace_order(partially_refunded)

    # Act
    with pytest.raises(InvalidOrderStateError):
        await application.mediator.send(CancelOrderRequest(1))

    # Assert
    assert await application.database.orders() == [partially_refunded]
    assert application.inventory.releases == []
    assert application.payments.voids == []
    assert application.mailer.messages == []
    assert await application.events(AggregateType.ORDER, 1) == ()


async def test_refund_order_supports_partial_then_complete_refund(
    application: ApplicationHarness,
) -> None:
    # Arrange
    await application.seed_order()

    # Act
    partial = await application.mediator.send(RefundOrderRequest(1, 1_000))
    complete = await application.mediator.send(RefundOrderRequest(1, 2_000))

    # Assert
    assert partial.status == OrderStatus.PARTIALLY_REFUNDED.value
    assert complete.status == OrderStatus.REFUNDED.value
    assert complete.refunded_pence == 3_000
    assert application.payments.refunds == [(1, 1_000), (1, 2_000)]
    assert await application.database.customers() == []
    events = await application.events(AggregateType.ORDER, 1)
    assert [event.payload["amount_pence"] for event in events] == [1_000, 2_000]
    assert all(event.event_type == "orders.order-refunded" for event in events)


async def test_refund_order_rejects_excess_without_payment_or_credit(
    application: ApplicationHarness,
) -> None:
    # Arrange
    placed = await application.seed_order()

    # Act
    with pytest.raises(ExcessiveRefundError):
        await application.mediator.send(RefundOrderRequest(1, 3_001))

    # Assert
    assert await application.database.orders() == [placed]
    assert application.payments.refunds == []
    assert await application.database.customers() == []
    assert await application.events(AggregateType.ORDER, 1) == ()


async def test_request_export_only_enqueues_serializable_work(
    application: ApplicationHarness,
) -> None:
    # Arrange
    request = RequestOrderExportRequest(7, "jsonl")

    # Act
    job = await application.mediator.send(request)
    queued = await application.database.claim_outbox_messages(10, 120)

    # Assert
    assert job.job_id == queued[0].message_id
    assert queued[0].message.message.event_type == "shop.orders.order-export-requested"
    assert queued[0].message.message.payload == {"customer_id": 7, "format": "jsonl"}
    assert application.storage.exports == {}
    events = await application.events(AggregateType.CUSTOMER, 7)
    assert len(events) == 1
    assert events[0].event_type == "orders.export-requested"


async def test_request_export_rejects_unknown_format_before_enqueuing(
    application: ApplicationHarness,
) -> None:
    # Arrange
    request = RequestOrderExportRequest(7, "xml")

    # Act
    with pytest.raises(UnsupportedExportFormatError):
        await application.mediator.send(request)

    # Assert
    assert await application.database.claim_outbox_messages(10, 120) == ()
    assert await application.events(AggregateType.CUSTOMER, 7) == ()


async def test_order_history_is_projected_through_the_mediator(
    application: ApplicationHarness,
) -> None:
    # Arrange
    await application.mediator.send(CreateOrderRequest(7, (OrderItem("book", 1),)))

    # Act
    history = await application.mediator.send(GetOrderHistoryRequest(1))

    # Assert
    assert history.order_id == 1
    assert [entry.kind for entry in history.entries] == ["placed"]


async def test_confirmation_is_sent_idempotently_through_the_mediator(
    application: ApplicationHarness,
) -> None:
    # Arrange
    request = SendOrderConfirmationRequest(1, 7, "confirmation-message")

    # Act
    first = await application.mediator.send(request)
    second = await application.mediator.send(request)

    # Assert
    assert first == second
    assert first.order_id == 1
    assert application.mailer.messages == [("customer-7@example.com", "Order 1 placed")]


@pytest.mark.parametrize(
    ("format", "expected"),
    [
        ("csv", "order_id,total_pence,status\n1,3000,placed\n"),
        ("jsonl", '{"order_id":1,"total_pence":3000,"status":"placed"}\n'),
    ],
)
async def test_export_orders_streams_supported_formats(
    application: ApplicationHarness,
    format: str,
    expected: str,
) -> None:
    # Arrange
    await application.seed_order()

    # Act
    result = await application.mediator.send(ExportOrdersRequest(7, format))

    # Assert
    assert result.rows == 1
    assert result.url == f"memory://exports/7.{format}"
    assert application.storage.exports[7] == expected
    assert application.mailer.messages == [
        ("customer-7@example.com", f"Your order export is ready: memory://exports/7.{format}")
    ]
    assert await application.events(AggregateType.CUSTOMER, 7) == ()


async def test_export_orders_rejects_unknown_format_without_writing(
    application: ApplicationHarness,
) -> None:
    # Arrange
    await application.seed_order()

    # Act
    with pytest.raises(UnsupportedExportFormatError):
        await application.mediator.send(ExportOrdersRequest(7, "xml"))

    # Assert
    assert application.storage.exports == {}
    assert application.mailer.messages == []
    assert await application.events(AggregateType.CUSTOMER, 7) == ()
