"""The god service, run — each test pins down one of the four pains it grows into.

These tests *pass*: they assert that the pain is real. `test_after.py` is the mirror image,
asserting each pain resolved.
"""

import pytest

from orders.before.service import OrderService
from orders.domain import AuditLog, InventoryService, Mailer, OrderStore, PaymentGateway


def make_service() -> tuple[OrderService, AuditLog, OrderStore]:
    """Build an OrderService for a test.

    Pain #4, right here: to exercise *any* single operation, the test has to construct the
    whole world — all five collaborators — because that is what the constructor demands.
    """
    store = OrderStore()
    audit = AuditLog()
    service = OrderService(store, PaymentGateway(), Mailer(), InventoryService(), audit)
    return service, audit, store


async def test_a_mistyped_action_is_only_caught_at_runtime() -> None:
    # Pain #1: "exprot_orders" is a perfectly good str, so the type checker sees nothing
    # wrong with this call. It fails only when it runs — in a worker, at 2 a.m.
    service, _, _ = make_service()
    with pytest.raises(ValueError, match="unknown action"):
        await service.dispatch("exprot_orders", {"customer_id": 1})


async def test_the_dispatch_response_is_untyped() -> None:
    # Pain #2: dispatch returns Any, so `result.orderid` (a typo for order_id) is not a
    # type error. Nothing flags it; it blows up only when the attribute is read.
    service, _, _ = make_service()
    result = await service.dispatch("place_order", {"customer_id": 1, "items": ["book"]})
    with pytest.raises(AttributeError):
        _ = result.orderid  # the type checker stayed silent on this line


async def test_refunds_are_silently_missing_from_the_audit_trail() -> None:
    # Pain #3: auditing is copy-pasted into each method, and refund (added later) never got
    # the line. The trail has a hole, and nothing anywhere flagged the omission.
    service, audit, _ = make_service()
    order = await service.place_order(customer_id=1, items=["book"])
    await service.refund(order.order_id, amount=10)

    assert "place_order" in audit.entries
    assert "refund" not in audit.entries


async def test_one_operation_still_costs_five_collaborators() -> None:
    # Pain #4, stated: refund touches only the store and the payment gateway, yet there is
    # no way to build an OrderService — and therefore no way to test refund — without also
    # supplying a mailer, an inventory service, and an audit log it never uses.
    service, _, _ = make_service()
    order = await service.place_order(customer_id=1, items=["book"])

    refunded = await service.refund(order.order_id, amount=10)

    assert refunded.status == "refunded"
