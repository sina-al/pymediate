"""Drive the real mediator and DI graph through FastAPI over ASGI."""

from collections.abc import AsyncIterator
from datetime import date
from uuid import UUID

import httpx2
import pytest

from shop.application.invoices.create_invoice import CreateInvoiceRequest
from shop.bindings.loading import application_context
from shop.openapi.web import create_app


@pytest.fixture
async def client() -> AsyncIterator[httpx2.AsyncClient]:
    async with application_context() as container:
        app = create_app(container)
        transport = httpx2.ASGITransport(app=app)
        async with httpx2.AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


@pytest.fixture
async def invoiced_client() -> AsyncIterator[httpx2.AsyncClient]:
    """Yield an API whose application graph contains one worker-created invoice."""
    async with application_context() as container:
        await container.mediator().send(CreateInvoiceRequest(42, 7, 1_500, "invoice-message"))
        app = create_app(container)
        transport = httpx2.ASGITransport(app=app)
        async with httpx2.AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


async def test_article_use_cases_cross_the_http_seam(client: httpx2.AsyncClient) -> None:
    # Arrange
    today = date.today()

    # Act
    opened = await client.post("/customers", json={"customer_id": 7})
    created = await client.post(
        "/orders",
        json={"customer_id": 7, "items": [{"sku": "book", "quantity": 2}]},
    )
    refunded = await client.post("/orders/1/refund", json={"amount_pence": 1_500})
    exported = await client.post("/orders/exports/7")
    statement = await client.post(
        "/customers/7/statements",
        json={"year": today.year, "month": today.month, "currency": "EUR"},
    )

    # Assert
    assert opened.status_code == 201
    assert created.status_code == 201
    assert created.json()["total_pence"] == 3_000
    assert refunded.json()["status"] == "partially-refunded"
    assert exported.status_code == 202
    assert exported.json()["customer_id"] == 7
    UUID(exported.json()["job_id"])
    assert statement.json()["currency"] == "EUR"


async def test_domain_error_is_translated_at_the_http_edge(client: httpx2.AsyncClient) -> None:
    # Arrange
    request = {"amount_pence": 100}

    # Act
    response = await client.post("/orders/999/refund", json=request)

    # Assert
    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json() == {
        "type": "/problems/order-not-found",
        "title": "Order not found",
        "status": 404,
        "detail": "Order 999 does not exist.",
        "instance": "/orders/999/refund",
        "code": "order-not-found",
        "context": {"order_id": 999},
    }


async def test_missing_invoice_uses_the_invoice_domain_problem(client: httpx2.AsyncClient) -> None:
    # Arrange
    order_id = 999

    # Act
    response = await client.get(f"/invoices/orders/{order_id}")

    # Assert
    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["code"] == "invoice-not-found"
    assert response.json()["context"] == {"order_id": 999}


async def test_created_invoice_crosses_the_http_boundary(
    invoiced_client: httpx2.AsyncClient,
) -> None:
    # Arrange
    order_id = 42

    # Act
    response = await invoiced_client.get(f"/invoices/orders/{order_id}")

    # Assert
    assert response.status_code == 200
    assert response.json() == {
        "invoice_id": 1,
        "order_id": 42,
        "customer_id": 7,
        "total_pence": 1_500,
        "document_url": "memory://invoices/invoice-message.pdf",
    }


async def test_store_credit_crosses_the_http_boundary(client: httpx2.AsyncClient) -> None:
    # Arrange
    opened = await client.post("/customers", json={"customer_id": 7})

    # Act
    credited = await client.post("/customers/7/store-credit", json={"amount_pence": 500})

    # Assert
    assert opened.status_code == 201
    assert credited.status_code == 200
    assert credited.json() == {"customer_id": 7, "store_credit_pence": 500}


async def test_order_history_is_exposed_as_an_allowlisted_projection(
    client: httpx2.AsyncClient,
) -> None:
    # Arrange
    await client.post(
        "/orders",
        json={"customer_id": 7, "items": [{"sku": "book", "quantity": 1}]},
    )

    # Act
    response = await client.get("/orders/1/history")

    # Assert
    assert response.status_code == 200
    body = response.json()
    assert body["order_id"] == 1
    entries = body["entries"]
    assert [entry["kind"] for entry in entries] == ["placed"]
    assert "payload" not in entries[0]
    UUID(entries[0]["event_id"])


async def test_domain_rule_violation_is_problem_json_not_transport_validation(
    client: httpx2.AsyncClient,
) -> None:
    # Arrange
    unsupported_format = "xml"

    # Act
    response = await client.post("/orders/exports/7", params={"format": unsupported_format})

    # Assert
    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["code"] == "unsupported-export-format"
    assert response.json()["context"] == {
        "requested_format": "xml",
        "supported_formats": ["csv", "jsonl"],
    }


async def test_domain_state_conflict_is_not_reported_as_validation(
    client: httpx2.AsyncClient,
) -> None:
    # Arrange
    await client.post(
        "/orders",
        json={"customer_id": 7, "items": [{"sku": "book", "quantity": 1}]},
    )
    await client.post("/orders/1/refund", json={"amount_pence": 100})

    # Act
    response = await client.post("/orders/1/cancel")

    # Assert
    assert response.status_code == 409
    assert response.json()["code"] == "invalid-order-state"
    assert response.json()["context"] == {
        "operation": "cancelled",
        "state": "partially-refunded",
    }


async def test_customer_closure_conflict_and_success_cross_http_boundary(
    client: httpx2.AsyncClient,
) -> None:
    # Arrange
    await client.post("/customers", json={"customer_id": 7})
    await client.post(
        "/orders",
        json={"customer_id": 7, "items": [{"sku": "book", "quantity": 1}]},
    )

    # Act
    blocked = await client.delete("/customers/7")
    await client.post("/orders/1/cancel")
    closed = await client.delete("/customers/7")

    # Assert
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "customer-has-open-orders"
    assert closed.status_code == 204
    assert closed.content == b""


async def test_customer_account_existence_errors_are_problem_details(
    client: httpx2.AsyncClient,
) -> None:
    # Arrange
    opened = await client.post("/customers", json={"customer_id": 7})

    # Act
    duplicate = await client.post("/customers", json={"customer_id": 7})
    missing = await client.post("/customers/8/store-credit", json={"amount_pence": 500})

    # Assert
    assert opened.status_code == 201
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "customer-already-exists"
    assert missing.status_code == 404
    assert missing.json()["code"] == "customer-not-found"


@pytest.mark.parametrize(
    "body",
    [
        {"customer_id": 0, "items": [{"sku": "book", "quantity": 1}]},
        {"customer_id": 7, "items": []},
        {"customer_id": 7, "items": [{"sku": "book", "quantity": 0}]},
    ],
)
async def test_transport_validation_rejects_malformed_create_order(
    client: httpx2.AsyncClient,
    body: dict[str, object],
) -> None:
    # Arrange
    request = body

    # Act
    response = await client.post("/orders", json=request)

    # Assert
    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/json")


def test_app_factory_loads_the_container_named_by_yaml(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    monkeypatch.setenv("SHOP_WIRING", "configuration/default.yaml")

    # Act
    app = create_app()

    # Assert
    assert app.state.container.mediator is not None


async def test_openapi_describes_dtos_and_operations(client: httpx2.AsyncClient) -> None:
    # Arrange
    expected_schemas = {
        "CreateOrderRequest",
        "CreateMonthlyStatementRequest",
        "OpenCustomerAccountRequest",
        "AdjustStoreCreditRequest",
        "GetOrderHistoryResponse",
    }

    # Act
    document = (await client.get("/openapi.json")).json()

    # Assert
    assert document["info"]["title"] == "PyMediate Hexagonal Shop"
    assert expected_schemas <= set(document["components"]["schemas"])
    assert document["paths"]["/orders"]["post"]["tags"] == ["orders"]
    assert document["paths"]["/orders/{order_id}/history"]["get"]["tags"] == ["orders"]
    conflict = document["paths"]["/orders/{order_id}/cancel"]["post"]["responses"]["409"]
    assert set(conflict["content"]) == {"application/problem+json"}
    assert (
        conflict["content"]["application/problem+json"]["schema"]["title"]
        == "ProblemDetailsResponse"
    )
