"""Run the mediator through real PostgreSQL and MinIO Testcontainers."""

import asyncio
import os
from typing import cast

import pytest
from opentelemetry import trace
from testcontainers.minio import MinioContainer
from testcontainers.postgres import PostgresContainer

from shop.adapters.ephemeral import EphemeralMessageBroker
from shop.adapters.postgres import PostgresDbGateway
from shop.application.customers.open_customer_account import OpenCustomerAccountRequest
from shop.application.orders.create_order import CreateOrderRequest
from shop.application.orders.request_order_export import RequestOrderExportRequest
from shop.bindings.loading import create_application_container, load_wiring
from shop.domain.entities.orders import OrderItem
from shop.worker.consumer import MediatorMessageConsumer
from shop.worker.registry import decode_message
from shop.worker.relay import OutboxRelay


@pytest.mark.containers
async def test_real_postgres_and_minio_through_mediator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    if os.environ.get("RUN_TESTCONTAINERS") != "1":
        pytest.skip("set RUN_TESTCONTAINERS=1 to run Docker integrations")

    # Act
    with (
        PostgresContainer("postgres:17-alpine", driver=None) as postgres,
        MinioContainer("minio/minio:RELEASE.2025-04-22T22-12-26Z") as minio,
    ):
        minio.get_client().make_bucket("shop-exports")
        config = minio.get_config()
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", config["access_key"])
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", config["secret_key"])

        monkeypatch.setenv("SHOP_POSTGRES_URL", postgres.get_connection_url())
        monkeypatch.setenv("SHOP_S3_BUCKET", "shop-exports")
        monkeypatch.setenv("SHOP_S3_ENDPOINT", f"http://{config['endpoint']}")
        wiring = load_wiring("configuration/aws.yaml")
        async with wiring.activate("application"):
            container = create_application_container(wiring)
            mediator = container.mediator()
            await mediator.send(OpenCustomerAccountRequest(7))
            order = await mediator.send(CreateOrderRequest(7, (OrderItem("book", 2),)))
            await mediator.send(RequestOrderExportRequest(7))
            database = cast("PostgresDbGateway", container.database())
            broker = EphemeralMessageBroker()
            published = await OutboxRelay(database, broker).run_once()
            consumer = MediatorMessageConsumer(
                broker,
                database,
                mediator,
                decode_message,
                trace.get_tracer("test.worker"),
            )
            consumed = [await consumer.run_once() for _ in range(3)]
            identities = await asyncio.gather(*(database.next_order_identity() for _ in range(20)))

        objects = list(minio.get_client().list_objects("shop-exports", prefix="exports/"))
        object_name = cast("str", objects[0].object_name)
        contents = (
            minio.get_client()
            .get_object("shop-exports", object_name)
            .data.startswith(b"order_id,total_pence,status")
        )

    # Assert
    assert order.total_pence == 3_000
    assert published == 3
    assert consumed == [True, True, True]
    assert len(objects) == 1
    assert contents
    assert len(set(identities)) == 20
