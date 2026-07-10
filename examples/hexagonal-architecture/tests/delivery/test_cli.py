"""The CLI doorway, exercised over the memory wiring."""

from typer.testing import CliRunner

from shop_app_memory.wiring import runtime
from shop_delivery.cli import build_cli

runner = CliRunner()


def test_demo_runs_a_full_session() -> None:
    result = runner.invoke(build_cli(runtime), ["demo"])

    assert result.exit_code == 0
    assert "Registered Ada" in result.output
    assert "Placed order" in result.output
    assert "Refunded 3998 cents via store_credit" in result.output
    assert "Exported 1 orders" in result.output


def test_register_customer_prints_id() -> None:
    result = runner.invoke(build_cli(runtime), ["register-customer", "Ada", "ada@example.com"])

    assert result.exit_code == 0
    assert result.output.startswith("Registered Ada (")


def test_domain_errors_exit_nonzero_with_message() -> None:
    result = runner.invoke(build_cli(runtime), ["cancel-order", "missing"])

    assert result.exit_code == 1
    assert "Error: No order with id missing" in result.stderr
