"""Local mail adapter."""

from dataclasses import dataclass, field

from shop.ports.orders.cancel_order import CancelOrderMailer
from shop.ports.orders.export_orders import ExportOrdersMailer
from shop.ports.orders.refund_order import RefundOrderMailer
from shop.ports.orders.send_order_confirmation import SendOrderConfirmationMailer


@dataclass
class ConsoleMailer(
    SendOrderConfirmationMailer,
    CancelOrderMailer,
    RefundOrderMailer,
    ExportOrdersMailer,
):
    """Collect mail in a visible local outbox."""

    messages: list[tuple[str, str]] = field(default_factory=list)
    idempotency_keys: set[str] = field(default_factory=set)

    async def send(self, recipient: str, subject: str, idempotency_key: str | None = None) -> None:
        if idempotency_key is not None and idempotency_key in self.idempotency_keys:
            return
        if idempotency_key is not None:
            self.idempotency_keys.add(idempotency_key)
        self.messages.append((recipient, subject))

    async def send_export_ready(
        self,
        recipient: str,
        download_url: str,
        idempotency_key: str | None = None,
    ) -> None:
        """Record one export-ready message unless its durable request was seen before."""
        await self.send(
            recipient,
            f"Your order export is ready: {download_url}",
            idempotency_key=idempotency_key,
        )
