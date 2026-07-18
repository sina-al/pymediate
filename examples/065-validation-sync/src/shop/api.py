"""Validate request-body schemas at the HTTP boundary, then map them to commands.

This is the only module that imports Pydantic or FastAPI. It does two jobs:

1. **Schema validation** — a Pydantic model rejects JSON with missing fields or invalid field
   types with an automatic HTTP 422, before anything reaches the core.
2. **Mapping to a command** — direct field copying for ``/subscriptions`` and a structural
   transformation for ``/orders``.

Endpoints are plain ``def`` functions (FastAPI runs them in a threadpool) because the core
is synchronous — the async mirror of this example uses ``async def``. Business rules are
not checked here; the core raises ``ValidationError`` and the handler below maps it to a 422.
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

# ---- Direct mapping: the body model and command have matching fields ----


class SubscribeBody(BaseModel):
    """HTTP request body for starting a subscription."""

    email: str
    plan: str = "free"


# ---- Transformed mapping: the body model and command have different structures ----


class LineBody(BaseModel):
    """HTTP request-body data for one order line."""

    sku: str
    quantity: int


class OrderBody(BaseModel):
    """HTTP request body for an order, with nested item data."""

    customer_email: str
    items: list[LineBody]


def create_app() -> FastAPI:
    """Build a FastAPI app whose endpoints validate body schemas, then dispatch commands."""
    app = FastAPI(title="Shop")
    mediator = build_mediator()

    @app.exception_handler(ValidationError)
    def on_business_rule_error(request: HTTPRequest, error: ValidationError) -> JSONResponse:
        # A business-rule failure from the core surfaces as 422, like a schema failure.
        return JSONResponse(status_code=422, content={"errors": error.errors})

    @app.post("/subscriptions", status_code=201)
    def subscribe(body: SubscribeBody) -> Subscription:
        # Direct mapping: copy matching fields from one distinct type to another.
        return mediator.send(Subscribe(email=body.email, plan=body.plan))

    @app.post("/orders", status_code=201)
    def place_order(body: OrderBody) -> Order:
        # Transformed mapping: rename fields and convert nested lists to domain values.
        command = PlaceOrder(
            customer=body.customer_email,
            lines=tuple(OrderLine(sku=item.sku, quantity=item.quantity) for item in body.items),
        )
        return mediator.send(command)

    return app


app = create_app()
