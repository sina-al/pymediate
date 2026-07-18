"""Commands, business rules, and a validation behavior without web dependencies.

This module validates business rules such as the supported plans and the requirement that an
order contain a line. ``api.py`` validates the request-body schema. Commands carry data from
that boundary into this module without importing Pydantic or FastAPI here.

Two mechanisms for core validation appear here:

- ``Subscribe`` validates in ``__post_init__`` — the rule applies whenever the value exists, so
  the command refuses to exist in an invalid state.
- ``PlaceOrder`` is validated by a ``ValidationBehavior`` at dispatch time — its several rules
  live in a reusable, registered validator rather than the dataclass body.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pymediate import Mediator, PipelineBehavior, Request, RequestHandler, Services

# The supported plans are a business rule, not an HTTP schema rule.
KNOWN_PLANS = ("free", "pro")


class ValidationError(Exception):
    """One or more business rules failed. The HTTP boundary maps this to 422.

    Distinct from ``pydantic.ValidationError`` (which lives at the edge): this one carries
    business-rule messages and never depends on a web framework.
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
    """One line of an order in the transport-independent core."""

    sku: str
    quantity: int


@dataclass(frozen=True)
class Order:
    """A placed order."""

    order_id: int
    customer: str
    lines: tuple[OrderLine, ...]


# ---- Directly mapped command with construction-time validation ----


@dataclass
class Subscribe(Request[Subscription]):
    """Start a subscription from directly copied request-body fields.

    ``SubscribeBody`` and ``Subscribe`` are distinct types with matching fields. The business
    rules are checked here in ``__post_init__``.
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


# ---- Structurally transformed command with behavior-based validation ----


@dataclass
class PlaceOrder(Request[Order]):
    """Place an order after ``OrderBody`` has been transformed into domain values.

    Business rules are checked by ``ValidationBehavior`` during dispatch rather than in
    ``__post_init__``.
    """

    customer: str
    lines: tuple[OrderLine, ...]


# ---- The validation behavior: run registered validators before the handler ----

Validator = Callable[[Any], list[str]]


def validate_place_order(request: PlaceOrder) -> list[str]:
    """Return the failed business rules for placing an order."""
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

    Validators are keyed by request type and run before ``next()``. A request with no
    registered validator continues to its handler.
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
