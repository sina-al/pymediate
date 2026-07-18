"""Exercise the complete outbox, broker, inbox, and mediator worker pipeline."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import cast

from shop.adapters.ephemeral import (
    ConsoleMailer,
    EphemeralMessageBroker,
    EphemeralStorage,
    SqliteDbGateway,
)
from shop.application.container import ApplicationContainer
from shop.application.customers.open_customer_account import OpenCustomerAccountRequest
from shop.application.orders.create_order import CreateOrderRequest
from shop.application.orders.request_order_export import RequestOrderExportRequest
from shop.bindings.loading import create_application_container, load_wiring
from shop.domain.entities.orders import OrderItem
from shop.worker.app import (
    create_consumer_container,
    create_relay_container,
    run_consumer_once,
    run_relay_once,
)
from shop.worker.container import ConsumerContainer, RelayContainer


@asynccontextmanager
async def deployment() -> AsyncIterator[
    tuple[ApplicationContainer, RelayContainer, ConsumerContainer]
]:
    wiring = load_wiring()
    async with wiring.activate("application", "relay", "consumer"):
        application = create_application_container(wiring)
        relay = create_relay_container(wiring)
        consumer = create_consumer_container(wiring, application)
        yield application, relay, consumer


async def test_worker_roles_report_empty_sources() -> None:
    # Arrange
    deployment_context = deployment()

    # Act
    async with deployment_context as (_, relay, consumer):
        published = await run_relay_once(relay)
        consumed = await run_consumer_once(consumer)

    # Assert
    assert published == 0
    assert not consumed


async def test_order_events_create_confirmation_and_invoice_once() -> None:
    # Arrange
    deployment_context = deployment()

    # Act
    async with deployment_context as (application, relay, consumer):
        mediator = application.mediator()
        await mediator.send(OpenCustomerAccountRequest(7))
        await mediator.send(CreateOrderRequest(7, (OrderItem("book", 1),)))
        published = await run_relay_once(relay)
        consumed = [await run_consumer_once(consumer) for _ in range(2)]
        mailer = cast("ConsoleMailer", application.mailer())
        database = cast("SqliteDbGateway", application.database())
        invoice = await database.get_invoice_for_order(1)

    # Assert
    assert published == 2
    assert consumed == [True, True]
    assert mailer.messages == [("customer-7@example.com", "Order 1 placed")]
    assert invoice.order_id == 1


async def test_duplicate_broker_delivery_dispatches_each_external_effect_once() -> None:
    # Arrange
    deployment_context = deployment()

    # Act
    async with deployment_context as (application, relay, consumer):
        mediator = application.mediator()
        await mediator.send(OpenCustomerAccountRequest(7))
        await mediator.send(CreateOrderRequest(7, (OrderItem("book", 1),)))
        database = cast("SqliteDbGateway", application.database())
        broker = cast("EphemeralMessageBroker", consumer.queue())
        duplicate = (await database.claim_outbox_messages(1, 120))[0]
        await database.release_outbox_message(duplicate.message_id, duplicate.lease_token)
        await run_relay_once(relay)
        await broker.publish(duplicate.message)
        consumed = [await run_consumer_once(consumer) for _ in range(3)]
        mailer = cast("ConsoleMailer", application.mailer())
        invoice = await database.get_invoice_for_order(1)

    # Assert
    assert consumed == [True, True, True]
    assert mailer.messages == [("customer-7@example.com", "Order 1 placed")]
    assert invoice.order_id == 1


async def test_export_event_stores_file_and_sends_download_link() -> None:
    # Arrange
    deployment_context = deployment()

    # Act
    async with deployment_context as (application, relay, consumer):
        mediator = application.mediator()
        await mediator.send(OpenCustomerAccountRequest(7))
        await mediator.send(CreateOrderRequest(7, (OrderItem("book", 1),)))
        await mediator.send(RequestOrderExportRequest(7, "jsonl"))
        published = await run_relay_once(relay)
        consumed = [await run_consumer_once(consumer) for _ in range(3)]
        storage = cast("EphemeralStorage", application.storage())
        mailer = cast("ConsoleMailer", application.mailer())

    # Assert
    assert published == 3
    assert consumed == [True, True, True]
    assert storage.exports[7].startswith('{"order_id":1')
    assert mailer.messages[-1][0] == "customer-7@example.com"
    assert mailer.messages[-1][1].startswith("Your order export is ready: memory://")
