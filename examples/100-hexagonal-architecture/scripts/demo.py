"""Run the complete default-profile Shop journey in one process."""

import asyncio
from typing import cast

from shop.adapters.ephemeral import ConsoleMailer, EphemeralStorage
from shop.application.customers.open_customer_account import OpenCustomerAccountRequest
from shop.application.invoices.get_invoice import GetInvoiceRequest
from shop.application.orders.create_order import CreateOrderRequest
from shop.application.orders.get_order_history import GetOrderHistoryRequest
from shop.application.orders.request_order_export import RequestOrderExportRequest
from shop.bindings.loading import create_application_container, load_wiring
from shop.domain.entities.orders import OrderItem
from shop.worker.app import (
    create_consumer_container,
    create_relay_container,
    run_consumer_once,
    run_relay_once,
)


async def run_demo() -> None:
    """Exercise HTTP-independent application and background paths together."""
    wiring = load_wiring()

    async with wiring.activate("application", "relay", "consumer"):
        application = create_application_container(wiring)
        relay = create_relay_container(wiring)
        consumer = create_consumer_container(wiring, application)
        mediator = application.mediator()

        customer = await mediator.send(OpenCustomerAccountRequest(customer_id=7))
        order = await mediator.send(
            CreateOrderRequest(customer_id=7, items=(OrderItem("book", 1), OrderItem("mug", 1)))
        )
        export = await mediator.send(
            RequestOrderExportRequest(customer_id=customer.customer_id, format="csv")
        )

        published = await run_relay_once(relay)
        consumed = 0
        while await run_consumer_once(consumer):
            consumed += 1

        invoice = await mediator.send(GetInvoiceRequest(order_id=order.order_id))
        history = await mediator.send(GetOrderHistoryRequest(order_id=order.order_id))
        storage = cast("EphemeralStorage", application.storage())
        mailer = cast("ConsoleMailer", application.mailer())

        if published != 3 or consumed != 3:
            raise RuntimeError(
                f"Expected three background messages; published {published}, consumed {consumed}"
            )

        print("Shop demonstration complete")
        print(f"  customer: {customer.customer_id}")
        print(f"  order: {order.order_id} ({order.total_pence} pence)")
        print(f"  invoice: {invoice.invoice_id} -> {invoice.document_url}")
        print(f"  export job: {export.job_id} -> memory://exports/{customer.customer_id}.csv")
        print(f"  journal: {', '.join(entry.kind for entry in history.entries)}")
        print(f"  mail: {len(mailer.messages)} idempotent messages")
        print(f"  export bytes: {len(storage.exports[customer.customer_id].encode())}")


if __name__ == "__main__":
    asyncio.run(run_demo())
