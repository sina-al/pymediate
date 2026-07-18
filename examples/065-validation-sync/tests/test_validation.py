"""Tests for schema validation, business rules, and request-to-command mapping."""

import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

from shop.api import create_app


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


# ---- Direct field mapping: /subscriptions ----


def test_subscribe_accepts_valid_input(client: TestClient) -> None:
    response = client.post("/subscriptions", json={"email": "a@b.com", "plan": "pro"})

    assert response.status_code == 201
    assert response.json() == {"email": "a@b.com", "plan": "pro"}


def test_subscribe_schema_error_is_rejected_at_boundary(client: TestClient) -> None:
    # 'email' is missing: Pydantic rejects the body schema before the core is reached.
    response = client.post("/subscriptions", json={"plan": "pro"})

    assert response.status_code == 422  # FastAPI/Pydantic validation error


def test_subscribe_business_rule_is_rejected_in_core(client: TestClient) -> None:
    # The body matches the schema, but 'gold' is not a supported plan — a rule the core
    # owns. The command's __post_init__ raises ValidationError, mapped to 422.
    response = client.post("/subscriptions", json={"email": "a@b.com", "plan": "gold"})

    assert response.status_code == 422
    assert "plan must be one of" in response.json()["errors"][0]


# ---- Structural transformation: /orders ----


def test_place_order_accepts_valid_input(client: TestClient) -> None:
    response = client.post(
        "/orders",
        json={"customer_email": "a@b.com", "items": [{"sku": "WIDGET", "quantity": 2}]},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["customer"] == "a@b.com"
    assert body["lines"] == [{"sku": "WIDGET", "quantity": 2}]


def test_place_order_schema_error_is_rejected_at_boundary(client: TestClient) -> None:
    # 'quantity' should be an integer; a non-numeric string fails schema validation.
    response = client.post(
        "/orders",
        json={"customer_email": "a@b.com", "items": [{"sku": "WIDGET", "quantity": "lots"}]},
    )

    assert response.status_code == 422


def test_place_order_business_rule_is_rejected_in_core(client: TestClient) -> None:
    # An empty list matches the schema, but "at least one line" is a business rule
    # enforced by ValidationBehavior in the core → 422.
    response = client.post("/orders", json={"customer_email": "a@b.com", "items": []})

    assert response.status_code == 422
    assert "at least one line" in " ".join(response.json()["errors"])


def test_place_order_quantity_ceiling_is_a_core_rule(client: TestClient) -> None:
    response = client.post(
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
