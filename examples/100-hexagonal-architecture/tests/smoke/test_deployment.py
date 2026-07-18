"""Exercise a running cloud profile exclusively through its public HTTP API."""

import asyncio
import os
from collections.abc import AsyncIterator
from uuid import uuid4

import httpx2
import pytest

pytestmark = [
    pytest.mark.smoke,
    pytest.mark.skipif(
        "SHOP_SMOKE_CLOUD" not in os.environ,
        reason="requires an already running Docker deployment",
    ),
]


@pytest.fixture
async def client() -> AsyncIterator[httpx2.AsyncClient]:
    base_url = os.getenv("SHOP_SMOKE_BASE_URL", "http://localhost:8000")
    async with httpx2.AsyncClient(base_url=base_url, timeout=10) as client:
        yield client


@pytest.fixture
def cloud() -> str:
    value = os.environ["SHOP_SMOKE_CLOUD"]
    if value not in {"aws", "azure"}:
        pytest.fail(f"Unsupported smoke-test cloud: {value}")
    return value


async def test_openapi_is_available(client: httpx2.AsyncClient) -> None:
    # Arrange
    endpoint = "/openapi.json"

    # Act
    response = await client.get(endpoint)

    # Assert
    assert response.status_code == 200
    assert response.json()["info"]["title"] == "PyMediate Hexagonal Shop"


async def test_domain_errors_cross_the_running_http_boundary(
    client: httpx2.AsyncClient,
) -> None:
    # Arrange
    missing_order_id = 2_000_000_000

    # Act
    response = await client.post(
        f"/orders/{missing_order_id}/refund",
        json={"amount_pence": 100},
    )

    # Assert
    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["code"] == "order-not-found"


async def test_order_reaches_the_cloud_queue_worker_and_object_storage(
    client: httpx2.AsyncClient,
    cloud: str,
) -> None:
    # Arrange
    customer_id = uuid4().int % 1_000_000_000 + 1
    expected_scheme = "s3://" if cloud == "aws" else "azblob://"

    # Act
    opened = await client.post("/customers", json={"customer_id": customer_id})
    created = await client.post(
        "/orders",
        json={"customer_id": customer_id, "items": [{"sku": "book", "quantity": 2}]},
    )
    assert created.status_code == 201, created.text
    order_id = created.json()["order_id"]

    invoice = None
    for _ in range(120):
        candidate = await client.get(f"/invoices/orders/{order_id}")
        if candidate.status_code != 404:
            invoice = candidate
            break
        await asyncio.sleep(0.5)

    # Assert
    assert opened.status_code == 201, opened.text
    assert invoice is not None, "invoice was not processed within 60 seconds"
    assert invoice.status_code == 200, invoice.text
    assert invoice.json()["order_id"] == order_id
    assert invoice.json()["customer_id"] == customer_id
    assert invoice.json()["total_pence"] == 3_000
    assert invoice.json()["document_url"].startswith(expected_scheme)
