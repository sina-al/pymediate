"""Send the confirmation represented by a durable order event."""

from dataclasses import dataclass

from pymediate import Request, RequestHandler

from shop.ports.orders.send_order_confirmation import SendOrderConfirmationMailer


@dataclass(frozen=True)
class SendOrderConfirmationResponse:
    """Confirm which order's mail request was accepted."""

    order_id: int


@dataclass(frozen=True)
class SendOrderConfirmationRequest(Request[SendOrderConfirmationResponse]):
    """Request one order-confirmation email."""

    order_id: int
    customer_id: int
    idempotency_key: str | None = None


class SendOrderConfirmationHandler(RequestHandler[SendOrderConfirmationRequest]):
    """Translate the application request into a mail-port call."""

    def __init__(self, mailer: SendOrderConfirmationMailer) -> None:
        self._mailer = mailer

    async def __call__(
        self, request: SendOrderConfirmationRequest
    ) -> SendOrderConfirmationResponse:
        await self._mailer.send(
            f"customer-{request.customer_id}@example.com",
            f"Order {request.order_id} placed",
            idempotency_key=request.idempotency_key,
        )
        return SendOrderConfirmationResponse(request.order_id)
