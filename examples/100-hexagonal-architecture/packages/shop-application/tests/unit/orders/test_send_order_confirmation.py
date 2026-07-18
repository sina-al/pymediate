"""Test confirmation mail by calling the handler directly."""

import pytest

from shop.application.orders.send_order_confirmation import (
    SendOrderConfirmationHandler,
    SendOrderConfirmationRequest,
)
from shop.ports.orders.send_order_confirmation import SendOrderConfirmationMailer

from ..support import autospec


async def test_confirmation_passes_message_id_as_idempotency_key() -> None:
    # Arrange
    mailer = autospec(SendOrderConfirmationMailer)
    handle = SendOrderConfirmationHandler(mailer)

    # Act
    result = await handle(SendOrderConfirmationRequest(1, 7, "message-1"))

    # Assert
    assert result.order_id == 1
    mailer.send.assert_awaited_once_with(
        "customer-7@example.com", "Order 1 placed", idempotency_key="message-1"
    )


async def test_confirmation_propagates_mail_failure() -> None:
    # Arrange
    mailer = autospec(SendOrderConfirmationMailer)
    mailer.send.side_effect = RuntimeError("mail unavailable")
    handle = SendOrderConfirmationHandler(mailer)

    # Act
    with pytest.raises(RuntimeError, match="mail unavailable"):
        await handle(SendOrderConfirmationRequest(1, 7, "message-1"))

    # Assert
    mailer.send.assert_awaited_once()
