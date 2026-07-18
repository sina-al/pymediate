"""What the CQRS split guarantees, proven on a handful of rows.

Most tests drive the projector **synchronously** — ``app.projector.drain()`` between a command
and a query — so they never depend on timing. One test starts the real background worker and
waits (with a bounded timeout) for the read model to catch up, proving the live loop and the
wake-up work end to end.
"""

import asyncio
from collections.abc import Iterator
from pathlib import Path

import pytest

from catalog.app import App, build_app
from catalog.domain import (
    AdjustStock,
    CreateProduct,
    GetInventoryReport,
    GetInventoryReportNaive,
    GetProduct,
    ProductNotFoundError,
    ProductView,
    SearchProducts,
    TierSummary,
)
from catalog.projection import wait_until_caught_up


@pytest.fixture
def app(tmp_path: Path) -> Iterator[App]:
    application = build_app(tmp_path)
    yield application
    application.close()


async def test_create_returns_a_minimal_ack_with_outbox_position(app: App) -> None:
    result = await app.mediator.send(CreateProduct(name="Keyboard", price=49.99, stock=10))
    assert result.product_id == 1
    assert result.outbox_position == 1


async def test_command_writes_domain_and_outbox_but_not_the_read_model(app: App) -> None:
    # The command commits to SQLite (a naive read off the write store sees it)...
    await app.mediator.send(CreateProduct(name="Keyboard", price=49.99, stock=10))
    naive = await app.mediator.send(GetInventoryReportNaive())
    assert sum(tier.product_count for tier in naive) == 1

    # ...but the DuckDB read model stays empty until the projector drains the outbox.
    assert app.read_store.checkpoint() == 0
    assert app.projector.drain() == 1
    assert app.read_store.checkpoint() == 1


async def test_read_is_stale_until_drained_then_shows_the_denormalized_view(app: App) -> None:
    created = await app.mediator.send(CreateProduct(name="Keyboard", price=49.99, stock=10))

    with pytest.raises(ProductNotFoundError):
        await app.mediator.send(GetProduct(product_id=created.product_id))

    app.projector.drain()

    view = await app.mediator.send(GetProduct(product_id=created.product_id))
    assert view == ProductView(
        product_id=1, name="Keyboard", price=49.99, stock=10, in_stock=True, price_tier="standard"
    )


async def test_stock_adjustment_projects_new_stock_and_in_stock(app: App) -> None:
    created = await app.mediator.send(CreateProduct(name="Keyboard", price=49.99, stock=10))
    app.projector.drain()

    await app.mediator.send(AdjustStock(product_id=created.product_id, delta=-10))
    app.projector.drain()

    view = await app.mediator.send(GetProduct(product_id=created.product_id))
    assert view.stock == 0
    assert view.in_stock is False


async def test_adjusting_missing_product_raises_without_writing_outbox(app: App) -> None:
    with pytest.raises(ProductNotFoundError, match="product not found: 999"):
        await app.mediator.send(AdjustStock(product_id=999, delta=1))

    assert app.read_store.checkpoint() == 0
    assert app.projector.drain() == 0
    assert await app.mediator.send(GetInventoryReportNaive()) == []


async def test_search_filters_to_in_stock_only(app: App) -> None:
    await app.mediator.send(CreateProduct(name="In stock", price=10.0, stock=5))
    await app.mediator.send(CreateProduct(name="Sold out", price=10.0, stock=0))
    app.projector.drain()

    everything = await app.mediator.send(SearchProducts())
    in_stock = await app.mediator.send(SearchProducts(in_stock_only=True))
    assert len(everything) == 2
    assert [view.name for view in in_stock] == ["In stock"]


async def test_inventory_report_rolls_up_by_tier(app: App) -> None:
    await app.mediator.send(CreateProduct(name="USB-C Cable", price=8.5, stock=200))  # budget
    await app.mediator.send(CreateProduct(name="Keyboard", price=49.99, stock=7))  # standard
    await app.mediator.send(CreateProduct(name="4K Monitor", price=329.0, stock=4))  # premium
    app.projector.drain()

    report = await app.mediator.send(GetInventoryReport())
    tiers = {tier.price_tier: tier for tier in report}
    assert set(tiers) == {"budget", "standard", "premium"}
    assert tiers["budget"].product_count == 1
    assert tiers["budget"].inventory_value == pytest.approx(1700.0)


async def test_naive_and_optimized_reports_agree(app: App) -> None:
    await app.mediator.send(CreateProduct(name="USB-C Cable", price=8.5, stock=200))
    await app.mediator.send(CreateProduct(name="Keyboard", price=49.99, stock=7))
    await app.mediator.send(CreateProduct(name="4K Monitor", price=329.0, stock=4))
    app.projector.drain()

    def rollup(rows: list[TierSummary]) -> dict[str, tuple[int, float, float]]:
        return {
            tier.price_tier: (
                tier.product_count,
                round(tier.inventory_value, 2),
                round(tier.avg_price, 2),
            )
            for tier in rows
        }

    optimized = await app.mediator.send(GetInventoryReport())
    naive = await app.mediator.send(GetInventoryReportNaive())
    assert rollup(optimized) == rollup(naive)


async def test_get_missing_product_raises(app: App) -> None:
    with pytest.raises(ProductNotFoundError):
        await app.mediator.send(GetProduct(product_id=999))


async def test_live_worker_catches_the_read_model_up(app: App) -> None:
    worker_task = asyncio.create_task(app.worker.run())
    try:
        created = await app.mediator.send(CreateProduct(name="Keyboard", price=49.99, stock=10))
        await wait_until_caught_up(app.read_store, created.outbox_position, timeout=2.0)
        view = await app.mediator.send(GetProduct(product_id=created.product_id))
        assert view.name == "Keyboard"
        assert app.read_store.checkpoint() >= created.outbox_position
    finally:
        await app.worker.stop()
        await worker_task
