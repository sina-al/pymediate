"""The core: commands, invariants, and a validation behavior — no web framework in sight.

This module is the whole point of the example's *placement* answer: it validates **business
invariants** (a plan must be one we sell; an order must have at least one line), and it does
so with **no import of Pydantic or FastAPI**. The edge (``api.py``) validates the *shape* of
untrusted input; the core validates what it *means*. The command is the contract between them.

Two mechanisms for core validation appear here, and both are legitimate:

- ``Subscribe`` validates in ``__post_init__`` — the invariant is intrinsic to the value, so
  the command refuses to exist in an invalid state.
- ``PlaceOrder`` is validated by a ``ValidationBehavior`` at dispatch time — the rules are
  richer and belong in a reusable, registered validator rather than the dataclass body.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pymediate import Mediator, PipelineBehavior, Request, RequestHandler, Services

# The set of plans we actually sell — a business fact, not a wire-format detail.
KNOWN_PLANS = ("free", "pro")


class ValidationError(Exception):
    """A broken business invariant. The edge maps this to HTTP 422.

    Distinct from ``pydantic.ValidationError`` (which lives at the edge): this one carries
    domain messages and never depends on any web framework.
    """

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


# ---- Value objects (responses) ----


@dataclass(frozen=True)
class Subscription:
    """A created subscription."""

    email: str
    plan: str


@dataclass(frozen=True)
class OrderLine:
    """One line of an order — a domain value object, not the wire shape."""

    sku: str
    quantity: int


@dataclass(frozen=True)
class Order:
    """A placed order."""

    order_id: int
    customer: str
    lines: tuple[OrderLine, ...]


# ---- Collapsed case: the command validates itself in __post_init__ ----


@dataclass
class Subscribe(Request[Subscription]):
    """Start a subscription. Wire shape and domain shape are the same, so the edge DTO maps
    to this command field-for-field. The invariant lives here, in ``__post_init__``.
    """

    email: str
    plan: str = "free"

    def __post_init__(self) -> None:
        errors: list[str] = []
        if "@" not in self.email:
            errors.append("email must contain '@'")
        if self.plan not in KNOWN_PLANS:
            errors.append(f"plan must be one of {KNOWN_PLANS}, got {self.plan!r}")
        if errors:
            raise ValidationError(errors)


# ---- Split case: the command carries a domain shape; a behavior validates it ----


@dataclass
class PlaceOrder(Request[Order]):
    """Place an order. The wire DTO (``api.OrderBody``) has a different shape and is mapped
    into this command by the adapter. Business rules are checked by ``ValidationBehavior``
    at dispatch, not in ``__post_init__`` — they're richer and reusable.
    """

    customer: str
    lines: tuple[OrderLine, ...]


# ---- The validation behavior: run registered validators before the handler ----

Validator = Callable[[Any], list[str]]


def validate_place_order(request: PlaceOrder) -> list[str]:
    """Business invariants for placing an order (transport-independent)."""
    errors: list[str] = []
    if "@" not in request.customer:
        errors.append("customer must be an email address")
    if not request.lines:
        errors.append("an order must have at least one line")
    for line in request.lines:
        if line.quantity < 1:
            errors.append(f"{line.sku}: quantity must be >= 1")
        if line.quantity > 100:
            errors.append(f"{line.sku}: quantity must be <= 100")
    return errors


class ValidationBehavior(PipelineBehavior[Request]):
    """Run registered validators before dispatch; raise ``ValidationError`` if any fail.

    The MediatR ``ValidationBehavior`` analog: validators are keyed by request type and run
    before ``next()``. A request with no registered validator passes straight through.
    """

    def __init__(self, validators: dict[type[Request[Any]], list[Validator]]) -> None:
        self._validators = validators

    async def __call__(self, request: Request[Any], next: Callable[[], Awaitable[Any]]) -> Any:
        errors: list[str] = []
        for validator in self._validators.get(type(request), []):
            errors.extend(validator(request))
        if errors:
            raise ValidationError(errors)
        return await next()


# ---- Handlers ----


class SubscribeHandler(RequestHandler[Subscribe]):
    """Create a subscription. By the time it runs, the command is already valid."""

    async def __call__(self, request: Subscribe) -> Subscription:
        return Subscription(email=request.email, plan=request.plan)


class PlaceOrderHandler(RequestHandler[PlaceOrder]):
    """Place an order. The ValidationBehavior guarantees the invariants already hold."""

    def __init__(self) -> None:
        self._next_id = 0

    async def __call__(self, request: PlaceOrder) -> Order:
        self._next_id += 1
        return Order(order_id=self._next_id, customer=request.customer, lines=request.lines)


def build_mediator() -> Mediator:
    """Wire the handlers and the validation behavior into a mediator."""
    validators: dict[type[Request[Any]], list[Validator]] = {
        PlaceOrder: [validate_place_order],
    }
    services = Services()
    services.add(ValidationBehavior(validators))  # registered first → outermost
    services.add(SubscribeHandler())
    services.add(PlaceOrderHandler())
    return Mediator(services.provider())
