"""Runtime tests for the request-handler implementation."""

from dataclasses import dataclass

import pytest
from pymediate.sync import HandlerNotFoundError, Request

from orders.after.operations import PlaceOrder, RefundOrder, RefundOrderHandler
from orders.after.wiring import build_mediator
from orders.domain import AuditLog, Order, OrderStore, PaymentGateway


@dataclass
class ArchiveOrder(Request[Order]):
    """An operation the team has named but not yet written a handler for."""

    order_id: int


def test_an_unhandled_request_is_a_named_diagnosis() -> None:
    # Dispatch is by request type. A request with no registered handler names that type.
    mediator = build_mediator()
    with pytest.raises(HandlerNotFoundError, match="ArchiveOrder"):
        mediator.send(ArchiveOrder(order_id=1))


def test_send_returns_the_declared_type() -> None:
    # PlaceOrder is a Request[Order], so send is statically typed to return Order.
    mediator = build_mediator()
    order = mediator.send(PlaceOrder(customer_id=1, items=["book"]))
    assert order.order_id == 1
    assert order.status == "placed"


def test_refund_is_audited_like_everything_else() -> None:
    # AuditBehavior records both requests after their handlers return successfully.
    store = OrderStore()
    audit = AuditLog()
    mediator = build_mediator(store=store, audit=audit)

    mediator.send(PlaceOrder(customer_id=1, items=["book"]))
    mediator.send(RefundOrder(order_id=1, amount=10))

    assert audit.entries == ["PlaceOrder", "RefundOrder"]


def test_a_handler_takes_only_what_it_uses() -> None:
    # RefundOrderHandler can be tested with only the store and payment gateway it uses.
    store = OrderStore()
    store.save(customer_id=1, items=["book"])
    handler = RefundOrderHandler(store, PaymentGateway())

    order = handler(RefundOrder(order_id=1, amount=10))

    assert order.status == "refunded"
