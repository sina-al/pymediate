"""The edge: Pydantic DTOs validate the *shape* of untrusted input, then map to commands.

This is the only module that imports Pydantic or FastAPI. It does two jobs:

1. **Shape validation** — a Pydantic model rejects malformed JSON (missing fields, wrong
   types) with an automatic HTTP 422, before anything reaches the core.
2. **Mapping DTO → command** — trivially when the wire shape equals the domain shape
   (``/subscriptions``), or with a real transformation when they differ (``/orders``).

Business invariants are *not* checked here. Those belong to the core, which raises
``ValidationError``; the exception handler below turns that into a 422 too — so both the
shape failure and the invariant failure look the same to the client, from different layers.
"""

from fastapi import FastAPI
from fastapi import Request as HTTPRequest
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .core import (
    Order,
    OrderLine,
    PlaceOrder,
    Subscribe,
    Subscription,
    ValidationError,
    build_mediator,
)

# ---- Collapsed case: the DTO mirrors the command field-for-field ----


class SubscribeBody(BaseModel):
    """Wire shape for starting a subscription — identical to the ``Subscribe`` command."""

    email: str
    plan: str = "free"


# ---- Split case: the DTO's shape differs from the domain command ----


class LineBody(BaseModel):
    """Wire shape for one order line."""

    sku: str
    quantity: int


class OrderBody(BaseModel):
    """Wire shape for an order — nested and named differently from the domain ``Order``."""

    customer_email: str
    items: list[LineBody]


def create_app() -> FastAPI:
    """Build a FastAPI app whose endpoints validate shape, then dispatch commands."""
    app = FastAPI(title="Shop")
    mediator = build_mediator()

    @app.exception_handler(ValidationError)
    async def on_invariant_error(request: HTTPRequest, error: ValidationError) -> JSONResponse:
        # A broken business invariant from the core surfaces as 422, like a shape failure.
        return JSONResponse(status_code=422, content={"errors": error.errors})

    @app.post("/subscriptions", status_code=201)
    async def subscribe(body: SubscribeBody) -> Subscription:
        # Collapsed: wire shape == domain shape, so the mapping is a trivial pass-through.
        return await mediator.send(Subscribe(email=body.email, plan=body.plan))

    @app.post("/orders", status_code=201)
    async def place_order(body: OrderBody) -> Order:
        # Split: translate the wire DTO into the domain command. The core never sees the DTO.
        command = PlaceOrder(
            customer=body.customer_email,
            lines=tuple(OrderLine(sku=item.sku, quantity=item.quantity) for item in body.items),
        )
        return await mediator.send(command)

    return app


app = create_app()
