"""Tests for HTTP and CLI mappings of domain errors."""

from collections.abc import AsyncIterator

import httpx2
import pytest
from fastapi import HTTPException

from shop.api import create_app
from shop.cli import EXIT_NOT_FOUND, EXIT_OK, EXIT_OUT_OF_STOCK, main, send_as_cli
from shop.core import GetProduct, build_mediator
from shop.leaky import LeakyGetProduct, build_leaky_mediator


@pytest.fixture
async def client() -> AsyncIterator[httpx2.AsyncClient]:
    transport = httpx2.ASGITransport(app=create_app())
    async with httpx2.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# ---- Transport 1: HTTP maps domain errors to status codes ----


async def test_http_get_missing_product_is_404(client: httpx2.AsyncClient) -> None:
    response = await client.get("/products/999")

    assert response.status_code == 404
    assert response.json() == {"error": "product not found: 999"}


async def test_http_out_of_stock_is_409(client: httpx2.AsyncClient) -> None:
    response = await client.post("/products/2/orders", params={"quantity": 3})

    assert response.status_code == 409
    assert "out of stock" in response.json()["error"]


async def test_http_valid_requests_succeed(client: httpx2.AsyncClient) -> None:
    assert (await client.get("/products/1")).status_code == 200
    assert (await client.post("/products/1/orders", params={"quantity": 2})).status_code == 201


# ---- Transport 2: the CLI maps the *same* errors to exit codes ----


def test_cli_missing_product_is_exit_3() -> None:
    assert main(["get", "999"]) == EXIT_NOT_FOUND


def test_cli_out_of_stock_is_exit_4() -> None:
    assert main(["order", "2", "3"]) == EXIT_OUT_OF_STOCK


def test_cli_valid_requests_return_exit_0() -> None:
    assert main(["get", "1"]) == EXIT_OK
    assert main(["order", "1", "2"]) == EXIT_OK


# ---- An HTTP-specific exception has no CLI mapping ----


def test_leaked_http_exception_escapes_the_cli() -> None:
    # The CLI mapping handles domain errors, not HTTP-specific exceptions.
    leaky = build_leaky_mediator()

    with pytest.raises(HTTPException):
        send_as_cli(leaky, LeakyGetProduct(product_id=999))


def test_domain_error_would_have_been_handled() -> None:
    # The domain error for the same missing product has an explicit exit-code mapping.
    assert send_as_cli(build_mediator(), GetProduct(product_id=999)) == EXIT_NOT_FOUND
