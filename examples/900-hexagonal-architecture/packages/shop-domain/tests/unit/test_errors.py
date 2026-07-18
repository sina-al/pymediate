"""Test the stable, safe structure shared by domain failures."""

import pytest

from shop.domain.errors.orders import ExcessiveRefundError, OrderNotFoundError


def test_domain_error_exposes_code_title_detail_and_context() -> None:
    # Arrange
    order_id = 42

    # Act
    error = OrderNotFoundError(order_id)

    # Assert
    assert error.code == "order-not-found"
    assert error.title == "Order not found"
    assert error.detail == "Order 42 does not exist."
    assert error.context == {"order_id": 42}
    assert str(error) == error.detail


def test_domain_error_context_cannot_be_mutated_at_a_boundary() -> None:
    # Arrange
    error = ExcessiveRefundError(requested_pence=2_000, available_pence=1_000)

    # Act
    with pytest.raises(TypeError) as raised:
        error.context["available_pence"] = 2_000  # type: ignore[index]

    # Assert
    assert "does not support item assignment" in str(raised.value)
