"""Tests for the validation-placement example.

The three claims per endpoint: a bad *shape* is rejected at the edge (Pydantic → 422), a
valid shape with a broken *invariant* is rejected in the core (→ 422), and the happy path
works. Plus: the core drags in no Pydantic.
"""

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


# ---- Collapsed case: /subscriptions (DTO == command) ----


async def test_subscribe_happy_path(client: httpx2.AsyncClient) -> None:
    response = await client.post("/subscriptions", json={"email": "a@b.com", "plan": "pro"})

    assert response.status_code == 201
    assert response.json() == {"email": "a@b.com", "plan": "pro"}


async def test_subscribe_bad_shape_rejected_at_edge(client: httpx2.AsyncClient) -> None:
    # 'email' is missing entirely: Pydantic rejects the shape before the core is reached.
    response = await client.post("/subscriptions", json={"plan": "pro"})

    assert response.status_code == 422  # FastAPI/Pydantic validation error


async def test_subscribe_broken_invariant_rejected_in_core(client: httpx2.AsyncClient) -> None:
    # Valid shape (both strings), but 'gold' is not a plan we sell — an invariant the core
    # owns. The command's __post_init__ raises ValidationError, mapped to 422.
    response = await client.post("/subscriptions", json={"email": "a@b.com", "plan": "gold"})

    assert response.status_code == 422
    assert "plan must be one of" in response.json()["errors"][0]


# ---- Split case: /orders (DTO mapped into a differently-shaped command) ----


async def test_place_order_happy_path(client: httpx2.AsyncClient) -> None:
    response = await client.post(
        "/orders",
        json={"customer_email": "a@b.com", "items": [{"sku": "WIDGET", "quantity": 2}]},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["customer"] == "a@b.com"
    assert body["lines"] == [{"sku": "WIDGET", "quantity": 2}]


async def test_place_order_bad_shape_rejected_at_edge(client: httpx2.AsyncClient) -> None:
    # 'quantity' should be an int; a string is the wrong shape → edge 422.
    response = await client.post(
        "/orders",
        json={"customer_email": "a@b.com", "items": [{"sku": "WIDGET", "quantity": "lots"}]},
    )

    assert response.status_code == 422


async def test_place_order_broken_invariant_rejected_in_core(client: httpx2.AsyncClient) -> None:
    # Valid shape (empty list is a valid list), but "at least one line" is a business rule
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


# ---- The core owes nothing to the edge ----


def test_core_imports_no_pydantic() -> None:
    # Import only the core in a fresh interpreter and prove Pydantic never loaded. Keeping
    # the wire library out of the core is the whole point of the split case.
    code = "import shop.core, sys; sys.exit(1 if 'pydantic' in sys.modules else 0)"
    result = subprocess.run([sys.executable, "-c", code], capture_output=True)
    assert result.returncode == 0, "shop.core must not import pydantic"
