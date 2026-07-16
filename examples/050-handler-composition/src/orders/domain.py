"""Value objects, messages, fake collaborators, and the sender seam.

Everything here is plumbing for the one idea in ``handlers.PlaceOrderHandler``: a handler
that needs other operations done doesn't *hold* the other handlers — it dispatches
requests through the mediator. To do that it needs something it can call ``send`` and
``publish`` on. The obvious candidate is the ``Mediator`` itself, but the mediator doesn't
exist yet when the handler is constructed — the mediator is built *from* the handlers, so
injecting it directly would be a chicken-and-egg cycle.

``Sender`` (the small interface the composing handler actually depends on) and
``LateBoundSender`` (a stand-in you register now and bind once the mediator exists) are how
we break that cycle cleanly. ``app.build_mediator`` shows the two extra lines it costs.
"""

from dataclasses import dataclass, field
from typing import Protocol, TypeVar

from pymediate import Event, Mediator, Request

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


# ---- Event: the "announce" side of composition ----


@dataclass
class OrderPlaced(Event):
    """Announces a completed order. Subscribers react; the order handler doesn't wait on them."""

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


# ---- The sender seam: what the composing handler depends on instead of the Mediator ----


class Sender(Protocol):
    """The slice of the mediator a composing handler needs: dispatch, nothing else.

    ``Mediator`` satisfies this structurally, and so does ``LateBoundSender``. Depending on
    this narrow interface — rather than the concrete ``Mediator`` — is what lets the handler
    be constructed before the mediator exists and swapped for a fake in a test.
    """

    async def send(self, request: Request[ResponseT]) -> ResponseT:
        """Dispatch a request to its handler and await the typed response."""
        ...

    async def publish(self, event: Event) -> None:
        """Publish an event to every subscribed handler."""
        ...


class LateBoundSender:
    """A ``Sender`` you register before the mediator exists, then ``bind`` once it does.

    This is the whole trick for breaking the construction cycle. The composing handler
    depends on this object, so it can go into the same ``Services`` the mediator is built
    from. Immediately after constructing the mediator you call ``bind`` to close the loop.
    Every dispatch simply forwards to the bound mediator.
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

    async def publish(self, event: Event) -> None:
        """Forward an event to the bound mediator."""
        await self._require().publish(event)
