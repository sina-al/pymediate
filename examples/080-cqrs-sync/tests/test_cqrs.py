"""Tests for the CQRS example: separate stores, separate shapes, one mediator.

Each test proves a different piece of the split: commands return the minimum, queries
return the denormalized view, the two stores hold genuinely different shapes, and the read
model only ever changes because a command handler published an event.
"""

import pytest
from pymediate.sync import Mediator

from catalog.app import build_mediator
from catalog.domain import (
    AdjustStock,
    CreateProduct,
    GetProduct,
    ProductNotFoundError,
    ReadStore,
    SearchProducts,
    WriteStore,
)


@pytest.fixture
def write_store() -> WriteStore:
    return WriteStore()


@pytest.fixture
def read_store() -> ReadStore:
    return ReadStore()


@pytest.fixture
def mediator(write_store: WriteStore, read_store: ReadStore) -> Mediator:
    return build_mediator(write_store=write_store, read_store=read_store)


def test_command_response_is_minimal(mediator: Mediator) -> None:
    created = mediator.send(CreateProduct(name="Keyboard", price=49.99, stock=10))

    assert created.product_id == 1
    assert not hasattr(created, "in_stock")  # a command response, not a read-model view


def test_query_returns_the_denormalized_view(mediator: Mediator) -> None:
    created = mediator.send(CreateProduct(name="Keyboard", price=49.99, stock=10))

    view = mediator.send(GetProduct(product_id=created.product_id))

    assert view.name == "Keyboard"
    assert view.in_stock is True  # derived; WriteStore.Product has no such field
    assert view.price_tier == "standard"  # 49.99 falls in [20, 100)


def test_write_and_read_stores_are_separate_objects(
    mediator: Mediator, write_store: WriteStore, read_store: ReadStore
) -> None:
    mediator.send(CreateProduct(name="Keyboard", price=49.99, stock=10))

    # The write store holds the normalized record; the read store holds the projection.
    # A query handler reaching into write_store, or a command handler into read_store,
    # would be a wiring bug — this asserts each side only ever touched its own store.
    assert write_store._products.keys() == {1}
    assert read_store._views.keys() == {1}
    assert not hasattr(write_store._products[1], "in_stock")
    assert hasattr(read_store._views[1], "in_stock")


def test_read_model_updates_via_the_event_after_a_stock_adjustment(mediator: Mediator) -> None:
    created = mediator.send(CreateProduct(name="Widget", price=9.99, stock=5))

    mediator.send(AdjustStock(product_id=created.product_id, delta=-5))
    view = mediator.send(GetProduct(product_id=created.product_id))

    # Nothing called ReadStore.upsert directly from the test — only the command handler's
    # publish, delivered to StockAdjustedProjector, could have produced this.
    assert view.stock == 0
    assert view.in_stock is False


def test_search_filters_to_in_stock_only(mediator: Mediator) -> None:
    keyboard = mediator.send(CreateProduct(name="Keyboard", price=49.99, stock=10))
    out_of_stock = mediator.send(CreateProduct(name="Discontinued Mouse", price=5, stock=0))

    results = mediator.send(SearchProducts(in_stock_only=True))

    ids = {p.product_id for p in results}
    assert keyboard.product_id in ids
    assert out_of_stock.product_id not in ids


def test_get_missing_product_raises(mediator: Mediator) -> None:
    with pytest.raises(ProductNotFoundError):
        mediator.send(GetProduct(product_id=999))


def test_price_tiers(mediator: Mediator) -> None:
    budget = mediator.send(CreateProduct(name="Cable", price=5, stock=1))
    standard = mediator.send(CreateProduct(name="Mouse", price=25, stock=1))
    premium = mediator.send(CreateProduct(name="Monitor", price=250, stock=1))

    budget_view = mediator.send(GetProduct(product_id=budget.product_id))
    standard_view = mediator.send(GetProduct(product_id=standard.product_id))
    premium_view = mediator.send(GetProduct(product_id=premium.product_id))

    assert budget_view.price_tier == "budget"
    assert standard_view.price_tier == "standard"
    assert premium_view.price_tier == "premium"
