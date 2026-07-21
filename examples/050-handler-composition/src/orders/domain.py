"""Value objects, messages, local service doubles, and the sender interface.

``PlaceOrderHandler`` dispatches requests through the mediator instead of holding the other
handlers. It depends on an object with ``send`` and ``publish`` methods. The mediator itself
does not exist until its handlers have been registered, so the sender is bound after mediator
construction.

``Sender`` defines the required interface. ``LateBoundSender`` can be registered first and
bound once the mediator exists. ``app.build_mediator`` shows that setup.
"""

from dataclasses import dataclass, field
from typing import Protocol, TypeVar

from pymediate import Mediator, Notification, Request

ResponseT = TypeVar("ResponseT")


# ---- Value objects the operations return ----


@dataclass(frozen=True)
class Reservation:
    """Proof that stock was set aside for an order."""

    sku: str
    quantity: int


@dataclass(frozen=True)
class Receipt:
    """Proof that a customer's card was charged."""

    customer_id: str
    amount_cents: int


@dataclass(frozen=True)
class Order:
    """A placed order — the result of composing a reservation and a payment."""

    order_id: int
    reservation: Reservation
    receipt: Receipt


# ---- Requests: the composing command, plus the two sub-requests it dispatches ----


@dataclass
class PlaceOrder(Request[Order]):
    """Place an order: reserve stock, take payment, announce the result. Responds Order."""

    customer_id: str
    sku: str
    quantity: int
    amount_cents: int


@dataclass
class ReserveStock(Request[Reservation]):
    """Set aside ``quantity`` of ``sku``; responds with a Reservation."""

    sku: str
    quantity: int


@dataclass
class ChargePayment(Request[Receipt]):
    """Charge a customer ``amount_cents``; responds with a Receipt."""

    customer_id: str
    amount_cents: int


# ---- Notification: the "announce" side of composition ----


@dataclass
class OrderPlaced(Notification):
    """Announce a completed order to subscribers before publication returns."""

    order_id: int
    customer_id: str


# ---- Fakes: stand-ins for a warehouse and a payment gateway ----


class OutOfStockError(Exception):
    """Raised when the warehouse can't cover a reservation."""


class PaymentDeclinedError(Exception):
    """Raised when the gateway declines a charge."""


@dataclass
class Warehouse:
    """In-memory stock levels — a stand-in for a real inventory service."""

    stock: dict[str, int] = field(default_factory=dict)


@dataclass
class PaymentGateway:
    """Records the charges it accepts — a stand-in for a real payment provider.

    ``declined`` lists customer ids whose cards should fail, so a test can drive the
    payment-failure path deterministically.
    """

    charged: list[Receipt] = field(default_factory=list)
    declined: set[str] = field(default_factory=set)


# ---- The sender interface used by the composing handler ----


class Sender(Protocol):
    """The slice of the mediator a composing handler needs: dispatch, nothing else.

    ``Mediator`` satisfies this structurally, and so does ``LateBoundSender``. Depending on
    this narrow interface — rather than the concrete ``Mediator`` — is what lets the handler
    be constructed before the mediator exists and swapped for a fake in a test.
    """

    async def send(self, request: Request[ResponseT]) -> ResponseT:
        """Dispatch a request to its handler and await the typed response."""
        ...

    async def publish(self, notification: Notification) -> None:
        """Publish a notification to every subscribed handler."""
        ...


class LateBoundSender:
    """A ``Sender`` you register before the mediator exists, then ``bind`` once it does.

    The composing handler can be registered with this object before the mediator exists.
    Calling ``bind`` after mediator construction supplies the final dispatch target.
    """

    def __init__(self) -> None:
        """Create an unbound sender; call ``bind`` before dispatching through it."""
        self._mediator: Mediator | None = None

    def bind(self, mediator: Mediator) -> None:
        """Attach the mediator that dispatches will forward to."""
        self._mediator = mediator

    def _require(self) -> Mediator:
        if self._mediator is None:
            raise RuntimeError("LateBoundSender.send/publish called before bind()")
        return self._mediator

    async def send(self, request: Request[ResponseT]) -> ResponseT:
        """Forward a request to the bound mediator and await its response."""
        return await self._require().send(request)

    async def publish(self, notification: Notification) -> None:
        """Forward a notification to the bound mediator."""
        await self._require().publish(notification)
