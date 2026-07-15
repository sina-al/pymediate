"""Tests for the sync handler-composition example.

The claims under test: (1) placing an order dispatches the two sub-requests and publishes
the event — no handler references another; (2) with no event loop the sub-requests run
sequentially; (3) a failing sub-request propagates and the order is never announced.
"""

import pytest
from pymediate.sync import Mediator

from orders.app import build_mediator
from orders.domain import (
    OutOfStockError,
    PaymentDeclinedError,
    PaymentGateway,
    PlaceOrder,
    Warehouse,
)


@pytest.fixture
def journal() -> list[str]:
    return []


@pytest.fixture
def warehouse() -> Warehouse:
    return Warehouse(stock={"WIDGET": 10})


@pytest.fixture
def gateway() -> PaymentGateway:
    return PaymentGateway()


@pytest.fixture
def mediator(warehouse: Warehouse, gateway: PaymentGateway, journal: list[str]) -> Mediator:
    return build_mediator(warehouse=warehouse, gateway=gateway, journal=journal)


def test_place_order_composes_sub_requests_and_event(
    mediator: Mediator, warehouse: Warehouse, gateway: PaymentGateway, journal: list[str]
) -> None:
    order = mediator.send(PlaceOrder("cust-1", sku="WIDGET", quantity=2, amount_cents=1999))

    # The composing handler dispatched both sub-requests: their effects are visible.
    assert order.reservation.quantity == 2
    assert warehouse.stock["WIDGET"] == 8  # ReserveStockHandler ran
    assert gateway.charged == [order.receipt]  # ChargePaymentHandler ran
    # ...and the event reached both subscribers.
    assert "email:sent cust-1" in journal
    assert f"analytics:recorded {order.order_id}" in journal


def test_sub_requests_run_sequentially(mediator: Mediator, journal: list[str]) -> None:
    mediator.send(PlaceOrder("cust-1", sku="WIDGET", quantity=1, amount_cents=500))

    # No event loop, so no overlap: charge only starts after reserve has finished. Diff this
    # against the async twin, where the two sub-requests are in flight at the same time.
    assert journal.index("charge:start cust-1") > journal.index("reserve:done WIDGET")


def test_out_of_stock_propagates_and_nothing_is_announced(
    mediator: Mediator, journal: list[str]
) -> None:
    with pytest.raises(OutOfStockError):
        mediator.send(PlaceOrder("cust-1", sku="WIDGET", quantity=99, amount_cents=500))

    # A sub-request's failure surfaces from send(PlaceOrder); the order is never announced.
    assert "place:done" not in journal
    assert not any(entry.startswith("email:sent") for entry in journal)


def test_declined_payment_propagates(warehouse: Warehouse, journal: list[str]) -> None:
    gateway = PaymentGateway(declined={"cust-broke"})
    mediator = build_mediator(warehouse=warehouse, gateway=gateway, journal=journal)

    with pytest.raises(PaymentDeclinedError):
        mediator.send(PlaceOrder("cust-broke", sku="WIDGET", quantity=1, amount_cents=500))

    assert "place:done" not in journal
