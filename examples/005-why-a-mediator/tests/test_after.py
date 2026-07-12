"""The same task via pymediate — each test is the answer to one pain in `test_before.py`."""

from dataclasses import dataclass

import pytest
from pymediate import HandlerNotFoundError, Request

from orders.after.operations import PlaceOrder, RefundOrder, RefundOrderHandler
from orders.after.wiring import build_mediator
from orders.domain import AuditLog, Order, OrderStore, PaymentGateway


@dataclass
class ArchiveOrder(Request[Order]):
    """An operation the team has named but not yet written a handler for."""

    order_id: int


async def test_an_unhandled_request_is_a_named_diagnosis() -> None:
    # Fix #1: dispatch is by type, not by a string you can mistype — a wrong name like
    # `ArchveOrder` would be a NameError your editor catches as you type it. And a request
    # no handler answers is refused up front with the offending type named and a remedy
    # spelled out: the typed counterpart of before/'s opaque "unknown action" ValueError.
    mediator = build_mediator()
    with pytest.raises(HandlerNotFoundError, match="ArchiveOrder"):
        await mediator.send(ArchiveOrder(order_id=1))


async def test_send_returns_the_declared_type() -> None:
    # Fix #2: PlaceOrder is a Request[Order], so `send` returns an Order. `order.order_id`
    # is autocompleted and type-checked; `order.orderid` would be a *static* error here,
    # caught before the code ever runs.
    mediator = build_mediator()
    order = await mediator.send(PlaceOrder(customer_id=1, items=["book"]))
    assert order.order_id == 1
    assert order.status == "placed"


async def test_refund_is_audited_like_everything_else() -> None:
    # Fix #3: one AuditBehavior wraps every request, so refund is audited automatically.
    # The hole the copy-paste left in the before/ trail is gone — for free.
    store = OrderStore()
    audit = AuditLog()
    mediator = build_mediator(store=store, audit=audit)

    await mediator.send(PlaceOrder(customer_id=1, items=["book"]))
    await mediator.send(RefundOrder(order_id=1, amount=10))

    assert audit.entries == ["PlaceOrder", "RefundOrder"]


async def test_a_handler_takes_only_what_it_uses() -> None:
    # Fix #4: refund's handler needs the store and the payment gateway, and nothing else —
    # so its test constructs exactly those two, not a whole world.
    store = OrderStore()
    store.save(customer_id=1, items=["book"])
    handler = RefundOrderHandler(store, PaymentGateway())

    order = await handler(RefundOrder(order_id=1, amount=10))

    assert order.status == "refunded"
