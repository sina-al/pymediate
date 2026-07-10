"""The orders domain: every use case exercised with plain fakes — no patching."""

from pathlib import Path

import pytest

from shop_adapter_memory.repositories import MemoryCustomerRepository, MemoryOrderRepository
from shop_adapter_memory.services import (
    LocalFileStorage,
    RecordingMailer,
    RecordingPaymentGateway,
)
from shop_core.errors import (
    CustomerNotFoundError,
    InvalidOrderStateError,
    OrderNotFoundError,
)
from shop_core.orders import (
    CancelOrder,
    CancelOrderHandler,
    ExportOrders,
    ExportOrdersHandler,
    PlaceOrder,
    PlaceOrderHandler,
    RefundOrder,
    RefundOrderHandler,
)
from shop_domain.customers import Customer
from shop_domain.orders import LineItem, Order, OrderStatus
from shop_domain.payments import RefundMethod

ITEMS = [LineItem(sku="widget", quantity=2, unit_price_cents=1999)]


@pytest.fixture
def orders() -> MemoryOrderRepository:
    return MemoryOrderRepository()


@pytest.fixture
def customers() -> MemoryCustomerRepository:
    repo = MemoryCustomerRepository()
    repo.add(Customer(customer_id="ada", name="Ada", email="ada@example.com"))
    return repo


def place(orders: MemoryOrderRepository, customers: MemoryCustomerRepository) -> Order:
    return PlaceOrderHandler(orders, customers)(PlaceOrder(customer_id="ada", items=ITEMS))


def test_place_order_stores_order_with_total(
    orders: MemoryOrderRepository, customers: MemoryCustomerRepository
) -> None:
    order = place(orders, customers)

    assert order.status is OrderStatus.PLACED
    assert order.total_cents == 3998
    assert orders.get(order.order_id) == order


def test_place_order_for_unknown_customer_raises(orders: MemoryOrderRepository) -> None:
    handler = PlaceOrderHandler(orders, MemoryCustomerRepository())

    with pytest.raises(CustomerNotFoundError):
        handler(PlaceOrder(customer_id="ghost", items=ITEMS))


def test_cancel_order_marks_cancelled(
    orders: MemoryOrderRepository, customers: MemoryCustomerRepository
) -> None:
    order = place(orders, customers)

    cancelled = CancelOrderHandler(orders)(CancelOrder(order_id=order.order_id))

    assert cancelled.status is OrderStatus.CANCELLED


def test_cancel_twice_raises(
    orders: MemoryOrderRepository, customers: MemoryCustomerRepository
) -> None:
    order = place(orders, customers)
    handler = CancelOrderHandler(orders)
    handler(CancelOrder(order_id=order.order_id))

    with pytest.raises(InvalidOrderStateError):
        handler(CancelOrder(order_id=order.order_id))


def test_cancel_unknown_order_raises(orders: MemoryOrderRepository) -> None:
    with pytest.raises(OrderNotFoundError):
        CancelOrderHandler(orders)(CancelOrder(order_id="missing"))


def test_refund_via_gateway_confirms_by_email(
    orders: MemoryOrderRepository, customers: MemoryCustomerRepository
) -> None:
    order = place(orders, customers)
    gateway = RecordingPaymentGateway()
    mailer = RecordingMailer()
    handler = RefundOrderHandler(orders, customers, gateway, mailer)

    refund = handler(RefundOrder(order_id=order.order_id))

    assert refund.method is RefundMethod.ORIGINAL_PAYMENT
    assert gateway.refunds == [(order.order_id, 3998)]
    assert orders.get(order.order_id).status is OrderStatus.REFUNDED  # type: ignore[union-attr]
    [(to, subject, _)] = mailer.outbox
    assert to == "ada@example.com"
    assert order.order_id in subject


def test_refund_to_store_credit_credits_customer_not_gateway(
    orders: MemoryOrderRepository, customers: MemoryCustomerRepository
) -> None:
    order = place(orders, customers)
    gateway = RecordingPaymentGateway()
    handler = RefundOrderHandler(orders, customers, gateway, RecordingMailer())

    refund = handler(RefundOrder(order_id=order.order_id, to_store_credit=True))

    assert refund.method is RefundMethod.STORE_CREDIT
    assert gateway.refunds == []
    assert customers.get("ada").store_credit_cents == 3998  # type: ignore[union-attr]


def test_refund_cancelled_order_raises(
    orders: MemoryOrderRepository, customers: MemoryCustomerRepository
) -> None:
    order = place(orders, customers)
    CancelOrderHandler(orders)(CancelOrder(order_id=order.order_id))
    handler = RefundOrderHandler(orders, customers, RecordingPaymentGateway(), RecordingMailer())

    with pytest.raises(InvalidOrderStateError):
        handler(RefundOrder(order_id=order.order_id))


def test_export_writes_csv_and_counts_rows(
    orders: MemoryOrderRepository, customers: MemoryCustomerRepository, tmp_path: Path
) -> None:
    place(orders, customers)
    place(orders, customers)
    handler = ExportOrdersHandler(orders, LocalFileStorage(tmp_path))

    result = handler(ExportOrders(customer_id="ada"))

    assert result.rows == 2
    exported = (tmp_path / "orders-ada.csv").read_text()
    assert exported.startswith("order_id,status,total_cents")
    assert exported.count("3998") == 2


def test_export_supports_json(
    orders: MemoryOrderRepository, customers: MemoryCustomerRepository, tmp_path: Path
) -> None:
    place(orders, customers)
    handler = ExportOrdersHandler(orders, LocalFileStorage(tmp_path))

    result = handler(ExportOrders(customer_id="ada", fmt="json"))

    assert result.rows == 1
    assert result.url.endswith("orders-ada.json")
