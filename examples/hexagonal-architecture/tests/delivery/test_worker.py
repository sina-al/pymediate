"""The worker doorway: a queued job becomes the same request the web would send."""

import os
from pathlib import Path

from shop_app_memory.wiring import build
from shop_core.customers import RegisterCustomer
from shop_core.orders import PlaceOrder
from shop_delivery.worker import handle_job
from shop_domain.orders import LineItem


def test_handle_job_runs_the_export(tmp_path: Path) -> None:
    os.environ["EXPORT_DIR"] = str(tmp_path)
    try:
        mediator, _ = build()
    finally:
        del os.environ["EXPORT_DIR"]
    customer = mediator.send(RegisterCustomer(name="Ada", email="ada@example.com"))
    mediator.send(
        PlaceOrder(
            customer_id=customer.customer_id,
            items=[LineItem(sku="widget", quantity=1, unit_price_cents=500)],
        )
    )

    result = handle_job(mediator, {"customer_id": customer.customer_id, "fmt": "csv"})

    assert result.rows == 1
    assert (tmp_path / f"orders-{customer.customer_id}.csv").exists()
