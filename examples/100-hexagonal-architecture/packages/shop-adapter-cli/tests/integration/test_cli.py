"""Exercise the colourful Typer CLI against the real mediator and local YAML wiring."""

import os
from datetime import UTC, date, datetime
from typing import cast
from unittest.mock import Mock, create_autospec
from uuid import UUID

import pytest
from pymediate import Mediator
from typer.testing import CliRunner, Result

from shop.application.customers.adjust_store_credit import (
    AdjustStoreCreditRequest,
    AdjustStoreCreditResponse,
)
from shop.application.invoices.get_invoice import GetInvoiceRequest, GetInvoiceResponse
from shop.application.orders.get_order_history import (
    GetOrderHistoryRequest,
    GetOrderHistoryResponse,
    OrderHistoryEntry,
)
from shop.bindings.loading import create_application_container, load_wiring
from shop.cli import app as cli_app
from shop.cli.app import cli
from shop.cli.context import CliContext


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def context() -> CliContext:
    wiring = load_wiring()
    container = create_application_container(wiring)
    return CliContext(container.mediator(), wiring=wiring)


def invoke(runner: CliRunner, context: CliContext, *args: str) -> Result:
    """Invoke the command tree without replacing the real application graph."""
    return runner.invoke(cli, list(args), obj=context, color=False)


@pytest.mark.parametrize(("configured", "expected"), [(None, "true"), ("false", "false")])
def test_entrypoint_disables_telemetry_unless_explicitly_configured(
    monkeypatch: pytest.MonkeyPatch,
    configured: str | None,
    expected: str,
) -> None:
    # Arrange
    command = Mock()
    monkeypatch.setattr(cli_app, "app", command)
    if configured is None:
        monkeypatch.setenv("OTEL_SDK_DISABLED", "test-placeholder")
        monkeypatch.delenv("OTEL_SDK_DISABLED", raising=False)
    else:
        monkeypatch.setenv("OTEL_SDK_DISABLED", configured)

    # Act
    cli_app.main()

    # Assert
    assert os.environ["OTEL_SDK_DISABLED"] == expected
    command.assert_called_once_with(prog_name="shop")


def test_help_exposes_commands_by_feature(runner: CliRunner, context: CliContext) -> None:
    # Arrange
    expected_groups = ("orders", "customers", "invoices", "statements")

    # Act
    result = invoke(runner, context, "--help")

    # Assert
    assert result.exit_code == 0
    assert all(group in result.output for group in expected_groups)
    assert "Shop" in result.output


def test_open_customer_renders_the_initial_balance(runner: CliRunner, context: CliContext) -> None:
    # Arrange
    arguments = ("customers", "open", "--customer", "7")

    # Act
    result = invoke(runner, context, *arguments)

    # Assert
    assert result.exit_code == 0
    assert "Customer account opened" in result.output
    assert "£0.00" in result.output


def test_credit_customer_renders_the_result(runner: CliRunner) -> None:
    # Arrange
    mediator = create_autospec(Mediator, instance=True)
    mediator.send.return_value = AdjustStoreCreditResponse(7, 500)
    isolated = CliContext(cast("Mediator", mediator))

    # Act
    result = invoke(
        runner,
        isolated,
        "customers",
        "credit",
        "--customer",
        "7",
        "--amount",
        "500",
    )

    # Assert
    mediator.send.assert_awaited_once_with(AdjustStoreCreditRequest(7, 500))
    assert result.exit_code == 0
    assert "Store credit updated" in result.output
    assert "£5.00" in result.output


def test_place_order_renders_a_success_card(runner: CliRunner, context: CliContext) -> None:
    # Arrange
    arguments = ("orders", "place", "--customer", "7", "book:2", "mug:1")

    # Act
    result = invoke(runner, context, *arguments)

    # Assert
    assert result.exit_code == 0
    assert "Order placed" in result.output
    assert "#1" in result.output
    assert "£39.00" in result.output


def test_export_commands_distinguish_inline_from_queued_work(
    runner: CliRunner, context: CliContext
) -> None:
    # Arrange
    queued_arguments = (
        "orders",
        "request-export",
        "--customer",
        "7",
        "--format",
        "jsonl",
    )
    inline_arguments = ("orders", "export", "--customer", "7", "--format", "csv")

    # Act
    queued = invoke(runner, context, *queued_arguments)
    inline = invoke(runner, context, *inline_arguments)

    # Assert
    assert queued.exit_code == 0
    assert "Export queued" in queued.output
    UUID(queued.output.split("Job", maxsplit=1)[1].split()[0])
    assert inline.exit_code == 0
    assert "Export ready" in inline.output
    assert "memory://exports/7.csv" in inline.output


def test_invoice_lookup_renders_the_public_response(runner: CliRunner) -> None:
    # Arrange
    mediator = create_autospec(Mediator, instance=True)
    mediator.send.return_value = GetInvoiceResponse(
        invoice_id=11,
        order_id=42,
        customer_id=7,
        total_pence=3_900,
        document_url="memory://invoices/42.pdf",
    )
    isolated = CliContext(cast("Mediator", mediator))

    # Act
    result = invoke(runner, isolated, "invoices", "get", "--order", "42")

    # Assert
    mediator.send.assert_awaited_once_with(GetInvoiceRequest(42))
    assert result.exit_code == 0
    assert "Invoice found" in result.output
    assert "#11" in result.output
    assert "#42" in result.output
    assert "#7" in result.output
    assert "£39.00" in result.output
    assert "memory://invoices/42.pdf" in result.output


def test_missing_invoice_is_rendered_as_a_business_failure(
    runner: CliRunner, context: CliContext
) -> None:
    # Arrange
    arguments = ("invoices", "get", "--order", "404")

    # Act
    result = invoke(runner, context, *arguments)

    # Assert
    assert result.exit_code == 1
    assert "Invoice not found" in result.output
    assert "No invoice exists for order 404." in result.output
    assert "Traceback" not in result.output


def test_order_history_renders_the_public_projection(runner: CliRunner) -> None:
    # Arrange
    occurred_at = datetime(2026, 7, 18, 10, 30, tzinfo=UTC)
    response = GetOrderHistoryResponse(
        order_id=42,
        entries=(
            OrderHistoryEntry("placed-event", "placed", occurred_at),
            OrderHistoryEntry(
                "refund-event",
                "refunded",
                occurred_at,
                amount_pence=500,
                refunded_pence=500,
                status="partially-refunded",
            ),
            OrderHistoryEntry(
                "cancelled-event",
                "cancelled",
                occurred_at,
                status="cancelled",
            ),
        ),
    )
    mediator = create_autospec(Mediator, instance=True)
    mediator.send.return_value = response
    isolated = CliContext(cast("Mediator", mediator))

    # Act
    result = invoke(runner, isolated, "orders", "history", "--order", "42")

    # Assert
    mediator.send.assert_awaited_once_with(GetOrderHistoryRequest(42))
    assert result.exit_code == 0
    assert "Order #42 history" in result.output
    assert "Placed" in result.output
    assert "Refunded" in result.output
    assert "Cancelled" in result.output
    assert "£5.00" in result.output
    assert "partially-refunded" in result.output


def test_order_history_has_an_explicit_empty_state(runner: CliRunner, context: CliContext) -> None:
    # Arrange
    arguments = ("orders", "history", "--order", "404")

    # Act
    result = invoke(runner, context, *arguments)

    # Assert
    assert result.exit_code == 0
    assert "Order #404 history" in result.output
    assert "No public history entries" in result.output


def test_create_statement_renders_a_success_card(runner: CliRunner, context: CliContext) -> None:
    # Arrange
    today = date.today()

    # Act
    result = invoke(
        runner,
        context,
        "statements",
        "create",
        "--customer",
        "7",
        "--year",
        str(today.year),
        "--month",
        str(today.month),
        "--currency",
        "EUR",
    )

    # Assert
    assert result.exit_code == 0
    assert "Statement ready" in result.output
    assert f"memory://statements/7/{today.year:04d}-{today.month:02d}.pdf" in result.output
    assert "EUR" in result.output


@pytest.mark.parametrize("value", ["book", "book:not-a-number", "book:0"])
def test_invalid_item_has_a_cli_friendly_error(
    runner: CliRunner, context: CliContext, value: str
) -> None:
    # Arrange
    arguments = ("orders", "place", "--customer", "7", value)

    # Act
    result = invoke(runner, context, *arguments)

    # Assert
    assert result.exit_code == 2
    assert (
        "SKU:QUANTITY" in result.output
        or "invalid literal" in result.output
        or "positive" in result.output
    )


def test_domain_errors_are_rendered_without_a_traceback(
    runner: CliRunner, context: CliContext
) -> None:
    # Arrange
    arguments = ("orders", "place", "--customer", "7", "missing:1")

    # Act
    result = invoke(runner, context, *arguments)

    # Assert
    assert result.exit_code == 1
    assert "Product not found" in result.output
    assert "No product exists for SKU 'missing'." in result.output
    assert "Traceback" not in result.output
