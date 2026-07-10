"""What the application needs from the payment provider."""

from typing import Protocol


class PaymentGateway(Protocol):
    """The external payment provider, reduced to what the shop actually asks of it."""

    def refund(self, order_id: str, amount_cents: int) -> str:
        """Refund a charge to the original payment method; return the provider's reference."""
        ...
