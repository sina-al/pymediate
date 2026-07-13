"""Tests for the handler-composition example (sync).

Asserts the composing handler dispatches its sub-requests through the mediator (both
collaborators actually ran), that the result is assembled from both, and — the sync
difference — that the two sub-requests run sequentially, one fully finishing before the
next starts.
"""

import pytest
from pymediate.sync import Mediator

from taskboard.app import build_mediator
from taskboard.domain import OrderStore, ShippingRates, Warehouse
from taskboard.operations import PlaceOrder, QuoteShipping, ReserveStock


@pytest.fixture
def trace() -> list[str]:
    # One shared list both collaborators append to, so the recorded order is their real
    # execution order rather than two separate timelines.
    return []


@pytest.fixture
def warehouse(trace: list[str]) -> Warehouse:
    return Warehouse(trace=trace)


@pytest.fixture
def rates(trace: list[str]) -> ShippingRates:
    return ShippingRates(trace=trace)


@pytest.fixture
def store() -> OrderStore:
    return OrderStore()


@pytest.fixture
def mediator(warehouse: Warehouse, rates: ShippingRates, store: OrderStore) -> Mediator:
    return build_mediator(warehouse=warehouse, rates=rates, store=store)


def test_place_order_dispatches_both_sub_requests(
    mediator: Mediator, warehouse: Warehouse, rates: ShippingRates
) -> None:
    order = mediator.send(PlaceOrder(items=["pen", "notebook"]))

    # Both sub-handlers ran — the orchestrator dispatched to each through the mediator.
    assert warehouse.reserved == [["pen", "notebook"]]
    assert rates.quoted == [["pen", "notebook"]]
    # ...and the result is assembled from both sub-responses.
    assert order.reservation_id == "resv-1"
    assert order.shipping_cost == 10  # 5 per item, 2 items


def test_order_is_persisted(mediator: Mediator, store: OrderStore) -> None:
    order = mediator.send(PlaceOrder(items=["pen"]))

    assert store.orders == {order.order_id: order}


def test_sub_requests_run_sequentially(mediator: Mediator, trace: list[str]) -> None:
    mediator.send(PlaceOrder(items=["pen"]))

    # Sync has no concurrency: the first sub-request finishes completely before the second
    # starts. (The async twin overlaps them — diff the two to see the delivery difference.)
    assert trace == ["reserve:start", "reserve:done", "quote:start", "quote:done"]


def test_sub_requests_are_independently_dispatchable(mediator: Mediator) -> None:
    # The sub-requests aren't private to the orchestrator — they're first-class requests
    # anyone can send. Composition adds a caller, it doesn't hide the operations.
    reservation = mediator.send(ReserveStock(items=["glue"]))
    quote = mediator.send(QuoteShipping(items=["glue", "tape"]))

    assert reservation.reservation_id == "resv-1"
    assert quote.cost == 10
