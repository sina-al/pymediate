"""Tests for the sync error-handling example.

The core raises one domain error; each transport maps it its own way. The web edge turns
``ProductNotFoundError`` into 404 and ``OutOfStockError`` into 409; the CLI turns them into
exit codes 3 and 4. And the anti-pattern — a handler that raises ``HTTPException`` — breaks
the CLI, because a framework error isn't a domain error the CLI knows how to map.
"""

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from shop.api import create_app
from shop.cli import EXIT_NOT_FOUND, EXIT_OK, EXIT_OUT_OF_STOCK, main, send_as_cli
from shop.core import GetProduct, build_mediator
from shop.leaky import LeakyGetProduct, build_leaky_mediator


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


# ---- Transport 1: HTTP maps domain errors to status codes ----


def test_http_get_missing_product_is_404(client: TestClient) -> None:
    response = client.get("/products/999")

    assert response.status_code == 404
    assert response.json() == {"error": "product not found: 999"}


def test_http_out_of_stock_is_409(client: TestClient) -> None:
    response = client.post("/products/2/orders", params={"quantity": 3})

    assert response.status_code == 409
    assert "out of stock" in response.json()["error"]


def test_http_happy_path(client: TestClient) -> None:
    assert client.get("/products/1").status_code == 200
    assert client.post("/products/1/orders", params={"quantity": 2}).status_code == 201


# ---- Transport 2: the CLI maps the *same* errors to exit codes ----


def test_cli_missing_product_is_exit_3() -> None:
    assert main(["get", "999"]) == EXIT_NOT_FOUND


def test_cli_out_of_stock_is_exit_4() -> None:
    assert main(["order", "2", "3"]) == EXIT_OUT_OF_STOCK


def test_cli_happy_path_is_exit_0() -> None:
    assert main(["get", "1"]) == EXIT_OK
    assert main(["order", "1", "2"]) == EXIT_OK


# ---- The anti-pattern: a leaked framework error breaks the non-HTTP caller ----


def test_leaked_http_exception_escapes_the_cli() -> None:
    # The CLI mapping catches domain errors only. A handler that raises HTTPException defeats
    # it: the framework error sails past `except ProductNotFoundError` and crashes the job.
    leaky = build_leaky_mediator()

    with pytest.raises(HTTPException):
        send_as_cli(leaky, LeakyGetProduct(product_id=999))


def test_domain_error_would_have_been_handled() -> None:
    # Contrast: the correctly-written handler raises a domain error, which the CLI maps to a
    # clean exit code instead of crashing. Same missing product, opposite outcome.
    assert send_as_cli(build_mediator(), GetProduct(product_id=999)) == EXIT_NOT_FOUND
