"""Tests for schema validation, business rules, and request-to-command mapping."""

import subprocess
import sys
from collections.abc import AsyncIterator

import httpx2
import pytest

from shop.api import create_app


@pytest.fixture
async def client() -> AsyncIterator[httpx2.AsyncClient]:
    transport = httpx2.ASGITransport(app=create_app())
    async with httpx2.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# ---- Direct field mapping: /subscriptions ----


async def test_subscribe_accepts_valid_input(client: httpx2.AsyncClient) -> None:
    response = await client.post("/subscriptions", json={"email": "a@b.com", "plan": "pro"})

    assert response.status_code == 201
    assert response.json() == {"email": "a@b.com", "plan": "pro"}


async def test_subscribe_schema_error_is_rejected_at_boundary(client: httpx2.AsyncClient) -> None:
    # 'email' is missing: Pydantic rejects the body schema before the core is reached.
    response = await client.post("/subscriptions", json={"plan": "pro"})

    assert response.status_code == 422  # FastAPI/Pydantic validation error


async def test_subscribe_business_rule_is_rejected_in_core(client: httpx2.AsyncClient) -> None:
    # The body matches the schema, but 'gold' is not a supported plan — a rule the core
    # owns. The command's __post_init__ raises ValidationError, mapped to 422.
    response = await client.post("/subscriptions", json={"email": "a@b.com", "plan": "gold"})

    assert response.status_code == 422
    assert "plan must be one of" in response.json()["errors"][0]


# ---- Structural transformation: /orders ----


async def test_place_order_accepts_valid_input(client: httpx2.AsyncClient) -> None:
    response = await client.post(
        "/orders",
        json={"customer_email": "a@b.com", "items": [{"sku": "WIDGET", "quantity": 2}]},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["customer"] == "a@b.com"
    assert body["lines"] == [{"sku": "WIDGET", "quantity": 2}]


async def test_place_order_schema_error_is_rejected_at_boundary(
    client: httpx2.AsyncClient,
) -> None:
    # 'quantity' should be an integer; a non-numeric string fails schema validation.
    response = await client.post(
        "/orders",
        json={"customer_email": "a@b.com", "items": [{"sku": "WIDGET", "quantity": "lots"}]},
    )

    assert response.status_code == 422


async def test_place_order_business_rule_is_rejected_in_core(client: httpx2.AsyncClient) -> None:
    # An empty list matches the schema, but "at least one line" is a business rule
    # enforced by ValidationBehavior in the core → 422.
    response = await client.post("/orders", json={"customer_email": "a@b.com", "items": []})

    assert response.status_code == 422
    assert "at least one line" in " ".join(response.json()["errors"])


async def test_place_order_quantity_ceiling_is_a_core_rule(client: httpx2.AsyncClient) -> None:
    response = await client.post(
        "/orders",
        json={"customer_email": "a@b.com", "items": [{"sku": "WIDGET", "quantity": 9999}]},
    )

    assert response.status_code == 422
    assert "quantity must be <= 100" in " ".join(response.json()["errors"])


# ---- The core has no HTTP validation dependency ----


def test_core_imports_no_pydantic() -> None:
    # Import only the core in a fresh interpreter and confirm Pydantic never loaded.
    code = "import shop.core, sys; sys.exit(1 if 'pydantic' in sys.modules else 0)"
    result = subprocess.run([sys.executable, "-c", code], capture_output=True)
    assert result.returncode == 0, "shop.core must not import pydantic"
