"""Prove the application feature containers compose through one mediator."""

from datetime import date
from typing import cast

import pytest

from shop.adapters.ephemeral import ConsoleMailer, EphemeralStorage, SqliteDbGateway
from shop.application.customers.adjust_store_credit import AdjustStoreCreditRequest
from shop.application.customers.close_customer_account import CloseCustomerAccountRequest
from shop.application.customers.open_customer_account import OpenCustomerAccountRequest
from shop.application.invoices.get_invoice import GetInvoiceRequest
from shop.application.orders.cancel_order import CancelOrderRequest
from shop.application.orders.create_order import CreateOrderRequest
from shop.application.orders.get_order_history import GetOrderHistoryRequest
from shop.application.orders.refund_order import RefundOrderRequest
from shop.application.orders.request_order_export import RequestOrderExportRequest
from shop.application.statements.create_monthly_statement import (
    CreateMonthlyStatementRequest,
)
from shop.bindings.loading import create_application_container, load_wiring
from shop.domain.entities.orders import OrderItem
from shop.domain.errors.customers import CustomerHasOpenOrdersError
from shop.domain.events.base import AggregateType
from shop.worker.app import (
    create_consumer_container,
    create_relay_container,
    run_consumer_once,
    run_relay_once,
)


async def test_ephemeral_adapter_runs_the_article_workflow() -> None:
    # Arrange
    wiring = load_wiring()

    async with wiring.activate("application", "relay", "consumer"):
        application = create_application_container(wiring)
        relay = create_relay_container(wiring)
        consumer = create_consumer_container(wiring, application)
        database = cast("SqliteDbGateway", application.database())
        storage = cast("EphemeralStorage", application.storage())
        mailer = cast("ConsoleMailer", application.mailer())
        mediator = application.mediator()

        # Act
        opened = await mediator.send(OpenCustomerAccountRequest(7))
        order = await mediator.send(
            CreateOrderRequest(customer_id=7, items=(OrderItem("book", 2), OrderItem("mug", 1)))
        )
        with pytest.raises(CustomerHasOpenOrdersError):
            await mediator.send(CloseCustomerAccountRequest(7))
        refunded = await mediator.send(RefundOrderRequest(order.order_id, amount_pence=3_900))
        second_order = await mediator.send(CreateOrderRequest(7, (OrderItem("book", 1),)))
        cancelled = await mediator.send(CancelOrderRequest(second_order.order_id))
        job = await mediator.send(RequestOrderExportRequest(customer_id=7, format="jsonl"))
        published = await run_relay_once(relay)
        consumed = 0
        while await run_consumer_once(consumer):
            consumed += 1
        invoice = await mediator.send(GetInvoiceRequest(order.order_id))
        credit = await mediator.send(AdjustStoreCreditRequest(7, 500))
        history = await mediator.send(GetOrderHistoryRequest(order.order_id))
        today = date.today()
        statement = await mediator.send(
            CreateMonthlyStatementRequest(7, today.year, today.month, "EUR")
        )
        await mediator.send(CloseCustomerAccountRequest(7))
        customers = await database.customers()
        customer_events = tuple(
            [event async for event in database.stream_domain_events(AggregateType.CUSTOMER, "7")]
        )

        # Assert
        assert opened.customer_id == 7
        assert order.total_pence == 3_900
        assert refunded.status == "refunded"
        assert cancelled.status == "cancelled"
        assert job.job_id
        assert published == 5
        assert consumed == 5
        assert invoice.total_pence == 3_900
        assert credit.store_credit_pence == 500
        assert storage.exports[7].startswith('{"order_id":1')
        assert any(
            "order export is ready: memory://exports/7.jsonl" in subject
            for _, subject in mailer.messages
        )
        assert statement.currency == "EUR"
        assert statement.order_count == 1
        assert statement.total_minor == 0
        assert [entry.kind for entry in history.entries] == ["placed", "refunded"]
        assert all(customer.customer_id != 7 for customer in customers)
        assert any(event.event_type == "orders.export-requested" for event in customer_events)
