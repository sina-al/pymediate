"""Test the UTC system clock adapter."""

from datetime import UTC, datetime
from unittest.mock import patch

from shop.adapters.common import SystemClock


def test_clock_returns_the_current_utc_date() -> None:
    # Arrange
    subject = SystemClock()

    with patch("shop.adapters.common.clock.datetime") as clock:
        clock.now.return_value = datetime(2026, 7, 15, 23, 59, tzinfo=UTC)

        # Act
        result = subject.today()

    # Assert
    assert result.isoformat() == "2026-07-15"
    clock.now.assert_called_once_with(UTC)
