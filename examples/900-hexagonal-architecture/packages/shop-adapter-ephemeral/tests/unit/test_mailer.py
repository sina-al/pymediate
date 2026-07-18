"""Test visible and idempotent local mail effects."""

from shop.adapters.ephemeral import ConsoleMailer


async def test_export_ready_mail_suppresses_duplicate_message_ids() -> None:
    # Arrange
    mailer = ConsoleMailer()

    # Act
    await mailer.send_export_ready(
        "customer-7@example.com",
        "memory://exports/7.csv",
        idempotency_key="message-1",
    )
    await mailer.send_export_ready(
        "customer-7@example.com",
        "memory://exports/7.csv",
        idempotency_key="message-1",
    )

    # Assert
    assert mailer.messages == [
        (
            "customer-7@example.com",
            "Your order export is ready: memory://exports/7.csv",
        )
    ]
