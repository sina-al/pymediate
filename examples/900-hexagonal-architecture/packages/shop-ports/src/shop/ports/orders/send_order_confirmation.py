"""Mailer port owned by the background order-confirmation use case."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class SendOrderConfirmationMailer(Protocol):
    """Send one idempotent order confirmation."""

    async def send(
        self, recipient: str, subject: str, idempotency_key: str | None = None
    ) -> None: ...
