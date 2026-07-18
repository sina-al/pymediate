"""Test deterministic statement exchange rates."""

import pytest

from shop.adapters.common import FixedExchangeRates


@pytest.mark.parametrize(
    ("currency", "expected"),
    [("GBP", 1_000), ("EUR", 1_170), ("USD", 1_350), ("eur", 1_170)],
)
async def test_fixed_rates_convert_supported_currencies(currency: str, expected: int) -> None:
    # Arrange
    rates = FixedExchangeRates()

    # Act
    converted = await rates.convert_from_gbp(1_000, currency)

    # Assert
    assert converted == expected


async def test_fixed_rates_reject_unknown_currency() -> None:
    # Arrange
    rates = FixedExchangeRates()

    # Act
    with pytest.raises(ValueError, match="unsupported statement currency: CAD") as raised:
        await rates.convert_from_gbp(1_000, "CAD")

    # Assert
    assert str(raised.value) == "unsupported statement currency: CAD"
