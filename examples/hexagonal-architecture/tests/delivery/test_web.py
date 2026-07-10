"""The web doorway, exercised over the memory wiring."""

import pytest
from flask.testing import FlaskClient

from shop_adapter_memory.services import MemoryJobQueue
from shop_app_memory.wiring import build
from shop_delivery.web import create_app


@pytest.fixture
def queue() -> MemoryJobQueue:
    return MemoryJobQueue()


@pytest.fixture
def client(queue: MemoryJobQueue) -> FlaskClient:
    mediator, _ = build()
    app = create_app(mediator, queue)
    app.testing = True
    return app.test_client()


def register(client: FlaskClient) -> str:
    response = client.post("/customers", json={"name": "Ada", "email": "ada@example.com"})
    assert response.status_code == 201
    return response.get_json()["customer_id"]


def place(client: FlaskClient, customer_id: str) -> str:
    response = client.post(
        "/orders",
        json={
            "customer_id": customer_id,
            "items": [{"sku": "widget", "quantity": 2, "unit_price_cents": 1999}],
        },
    )
    assert response.status_code == 201
    return response.get_json()["order_id"]


def test_register_and_fetch_customer(client: FlaskClient) -> None:
    customer_id = register(client)

    response = client.get(f"/customers/{customer_id}")

    assert response.status_code == 200
    assert response.get_json()["name"] == "Ada"


def test_unknown_customer_is_404(client: FlaskClient) -> None:
    response = client.get("/customers/ghost")

    assert response.status_code == 404
    assert "ghost" in response.get_json()["error"]


def test_place_order_returns_created_order(client: FlaskClient) -> None:
    customer_id = register(client)

    response = client.post(
        "/orders",
        json={
            "customer_id": customer_id,
            "items": [{"sku": "widget", "quantity": 2, "unit_price_cents": 1999}],
        },
    )

    assert response.status_code == 201
    body = response.get_json()
    assert body["status"] == "placed"
    assert body["customer_id"] == customer_id


def test_place_order_for_unknown_customer_is_404(client: FlaskClient) -> None:
    response = client.post("/orders", json={"customer_id": "ghost", "items": []})

    assert response.status_code == 404


def test_cancel_then_refund_is_409(client: FlaskClient) -> None:
    order_id = place(client, register(client))
    assert client.post(f"/orders/{order_id}/cancel").status_code == 200

    response = client.post(f"/orders/{order_id}/refund")

    assert response.status_code == 409
    assert "cancelled" in response.get_json()["error"]


def test_refund_to_store_credit_shows_up_on_customer(client: FlaskClient) -> None:
    customer_id = register(client)
    order_id = place(client, customer_id)

    refund = client.post(f"/orders/{order_id}/refund", json={"to_store_credit": True})

    assert refund.status_code == 200
    assert refund.get_json()["method"] == "store_credit"
    customer = client.get(f"/customers/{customer_id}").get_json()
    assert customer["store_credit_cents"] == 3998


def test_export_is_queued_not_executed(client: FlaskClient, queue: MemoryJobQueue) -> None:
    customer_id = register(client)

    response = client.post("/orders/export", json={"customer_id": customer_id})

    assert response.status_code == 202
    assert response.get_json() == {"status": "queued"}
    assert queue.jobs.get_nowait() == {"customer_id": customer_id, "fmt": "csv"}
