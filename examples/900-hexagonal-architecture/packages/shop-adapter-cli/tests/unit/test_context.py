"""Verify command groups share one typed context accessor."""

from typing import cast
from unittest.mock import Mock

import pytest
import typer
from pymediate import Mediator

from shop.cli.app import app
from shop.cli.context import CliContext, get_context


def test_get_context_returns_the_initialized_cli_context() -> None:
    # Arrange
    expected = CliContext(cast("Mediator", Mock(spec=Mediator)))
    context = typer.Context(typer.main.get_command(app), obj=expected)

    # Act
    actual = get_context(context)

    # Assert
    assert actual is expected


def test_get_context_rejects_an_uninitialized_cli_context() -> None:
    # Arrange
    context = typer.Context(typer.main.get_command(app))

    # Act
    with pytest.raises(RuntimeError) as raised:
        get_context(context)

    # Assert
    assert str(raised.value) == "Shop CLI context was not initialized"
