"""Runtime tests for the `OrderService` implementation."""

import pytest

from orders.before.service import OrderService
from orders.domain import AuditLog, InventoryService, Mailer, OrderStore, PaymentGateway


def make_service() -> tuple[OrderService, AuditLog, OrderStore]:
    """Build an `OrderService` with all five required collaborators."""
    store = OrderStore()
    audit = AuditLog()
    service = OrderService(store, PaymentGateway(), Mailer(), InventoryService(), audit)
    return service, audit, store


async def test_a_mistyped_action_is_only_caught_at_runtime() -> None:
    # The optional dispatcher accepts any str, including a misspelled action.
    service, _, _ = make_service()
    with pytest.raises(ValueError, match="unknown action"):
        await service.dispatch("exprot_orders", {"customer_id": 1})


async def test_the_dispatch_response_is_untyped() -> None:
    # dispatch returns Any, so static checking does not reject this misspelled attribute.
    service, _, _ = make_service()
    result = await service.dispatch("place_order", {"customer_id": 1, "items": ["book"]})
    with pytest.raises(AttributeError):
        _ = result.orderid  # the type checker stayed silent on this line


async def test_refunds_are_silently_missing_from_the_audit_trail() -> None:
    # Auditing is repeated in each method, and refund omits that call.
    service, audit, _ = make_service()
    order = await service.place_order(customer_id=1, items=["book"])
    await service.refund(order.order_id, amount=10)

    assert "place_order" in audit.entries
    assert "refund" not in audit.entries


async def test_service_construction_requires_all_five_collaborators() -> None:
    # refund uses the store and payment gateway, but OrderService construction also requires
    # a mailer, inventory service, and audit log.
    service, _, _ = make_service()
    order = await service.place_order(customer_id=1, items=["book"])

    refunded = await service.refund(order.order_id, amount=10)

    assert refunded.status == "refunded"
