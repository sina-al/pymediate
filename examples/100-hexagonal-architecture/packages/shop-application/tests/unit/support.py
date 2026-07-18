"""Shared construction helpers for direct handler unit tests."""

from typing import cast
from unittest.mock import MagicMock, create_autospec

from shop.ports.unit_of_work import UnitOfWork


def autospec(port: type[object]) -> MagicMock:
    """Create a strict instance mock from one outbound port protocol."""
    return cast("MagicMock", create_autospec(port, instance=True, spec_set=True))


def autospec_unit() -> MagicMock:
    """Create an autospecced unit of work configured as an async context manager."""
    unit = autospec(UnitOfWork)
    unit.__aenter__.return_value = unit
    return unit
