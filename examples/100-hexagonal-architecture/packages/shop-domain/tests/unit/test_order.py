"""Domain tests contain no mediator, container, or adapter machinery."""

from collections.abc import Callable
from datetime import date, datetime
from functools import partial

import pytest

from shop.domain.entities.orders import Order, OrderItem, OrderLine, OrderStatus, Product
from shop.domain.errors import DomainError, InvalidIdentifierError
from shop.domain.errors.orders import (
    EmptyOrderError,
    ExcessiveRefundError,
    InvalidOrderSnapshotError,
    InvalidOrderStateError,
    InvalidOrderTotalError,
    InvalidPriceError,
    InvalidQuantityError,
    InvalidSkuError,
)


def _placed_order() -> Order:
    return Order.place(1, 7, (OrderLine("book", 1, 1_500),), date(2026, 7, 13))


def _capture[ErrorT: DomainError](
    error_type: type[ErrorT], operation: Callable[[], object]
) -> ErrorT:
    try:
        operation()
    except error_type as error:
        return error
    raise AssertionError(f"{error_type.__name__} was not raised")


def test_order_owns_totals_and_refund_state() -> None:
    # Arrange
    order = Order.place(
        1,
        7,
        (OrderLine("book", 2, 1_500), OrderLine("mug", 1, 900)),
        date(2026, 7, 13),
    )

    # Act
    partially_refunded = order.refund(900)

    # Assert
    assert order.total_pence == 3_900
    assert partially_refunded.refunded_pence == 900
    assert partially_refunded.status is OrderStatus.PARTIALLY_REFUNDED


def test_full_refund_is_a_terminal_refunded_state() -> None:
    # Arrange
    order = _placed_order()

    # Act
    refunded = order.refund(1_500)
    caught = _capture(InvalidOrderStateError, refunded.cancel)

    # Assert
    assert refunded.refunded_pence == 1_500
    assert refunded.status is OrderStatus.REFUNDED
    assert caught.context == {"operation": "cancelled", "state": "refunded"}


def test_cancellation_is_an_explicit_terminal_transition() -> None:
    # Arrange
    order = _placed_order()

    # Act
    cancelled = order.cancel()
    caught = _capture(InvalidOrderStateError, lambda: cancelled.refund(100))

    # Assert
    assert cancelled.status is OrderStatus.CANCELLED
    assert caught.context == {"operation": "refunded", "state": "cancelled"}


@pytest.mark.parametrize("amount_pence", [0, -100, 1_501, True, "100", None])
def test_order_rejects_invalid_refunds(amount_pence: object) -> None:
    # Arrange
    order = _placed_order()

    # Act
    caught = _capture(
        ExcessiveRefundError,
        lambda: order.refund(amount_pence),  # type: ignore[arg-type]
    )

    # Assert
    assert caught.context == {"requested_pence": amount_pence, "available_pence": 1_500}


@pytest.mark.parametrize("sku", ["", "   ", 7])
def test_product_sku_must_be_non_empty_text(sku: object) -> None:
    # Arrange
    create_product = partial(Product, sku, 100)  # type: ignore[arg-type]

    # Act
    caught = _capture(InvalidSkuError, create_product)

    # Assert
    assert caught.context == {"sku": sku}


@pytest.mark.parametrize("price_pence", [0, -1, True])
def test_product_price_must_be_a_positive_integer(price_pence: int) -> None:
    # Arrange
    create_product = partial(Product, "book", price_pence)

    # Act
    caught = _capture(InvalidPriceError, create_product)

    # Assert
    assert caught.context == {"price_pence": price_pence}


@pytest.mark.parametrize("quantity", [0, -1, True])
def test_order_item_quantity_must_be_positive(quantity: int) -> None:
    # Arrange
    create_item = partial(OrderItem, "book", quantity)

    # Act
    caught = _capture(InvalidQuantityError, create_item)

    # Assert
    assert caught.context == {"quantity": quantity}


def test_order_item_validates_its_sku() -> None:
    # Arrange
    create_item = partial(OrderItem, "", 1)

    # Act
    caught = _capture(InvalidSkuError, create_item)

    # Assert
    assert caught.context == {"sku": ""}


@pytest.mark.parametrize(
    ("line", "error_type"),
    [
        (lambda: OrderLine("", 1, 100), InvalidSkuError),
        (lambda: OrderLine("book", 0, 100), InvalidQuantityError),
        (lambda: OrderLine("book", 1, 0), InvalidPriceError),
    ],
)
def test_order_line_validates_every_priced_value(
    line: Callable[[], OrderLine], error_type: type[DomainError]
) -> None:
    # Arrange
    create_line = line

    # Act
    caught = _capture(error_type, create_line)

    # Assert
    assert caught.code in {"invalid-sku", "invalid-quantity", "invalid-price"}


def test_order_requires_at_least_one_line() -> None:
    # Arrange
    place = partial(Order.place, 1, 7, (), date(2026, 7, 13))

    # Act
    caught = _capture(EmptyOrderError, place)

    # Assert
    assert caught.code == "empty-order"


def test_reconstructed_order_also_requires_at_least_one_line() -> None:
    # Arrange
    reconstruct = partial(Order, 1, 7, (), 0, date(2026, 7, 13))

    # Act
    caught = _capture(EmptyOrderError, reconstruct)

    # Assert
    assert caught.code == "empty-order"


@pytest.mark.parametrize(("order_id", "customer_id"), [(0, 7), (1, 0), (True, 7)])
def test_order_requires_positive_identifiers(order_id: int, customer_id: int) -> None:
    # Arrange
    place = partial(
        Order.place,
        order_id,
        customer_id,
        (OrderLine("book", 1, 100),),
        date(2026, 7, 13),
    )

    # Act
    caught = _capture(InvalidIdentifierError, place)

    # Assert
    assert caught.context["value"] in {order_id, customer_id}


def test_reconstructed_order_total_must_match_its_lines() -> None:
    # Arrange
    reconstruct = partial(Order, 1, 7, (OrderLine("book", 1, 100),), 99, date(2026, 7, 13))

    # Act
    caught = _capture(InvalidOrderTotalError, reconstruct)

    # Assert
    assert caught.context == {"total_pence": 99, "calculated_pence": 100}


@pytest.mark.parametrize("total_pence", [True, "100", None])
def test_reconstructed_order_total_must_be_an_integer(total_pence: object) -> None:
    # Arrange
    reconstruct = partial(
        Order,
        1,
        7,
        (OrderLine("book", 1, 100),),
        total_pence,  # type: ignore[arg-type]
        date(2026, 7, 13),
    )

    # Act
    caught = _capture(InvalidOrderTotalError, reconstruct)

    # Assert
    assert caught.context == {"total_pence": total_pence, "calculated_pence": 100}


def test_reconstructed_order_requires_a_business_date() -> None:
    # Arrange
    reconstruct = partial(
        Order,
        1,
        7,
        (OrderLine("book", 1, 100),),
        100,
        datetime(2026, 7, 13),  # type: ignore[arg-type]
    )

    # Act
    caught = _capture(InvalidOrderSnapshotError, reconstruct)

    # Assert
    assert "placed_on" in caught.detail


@pytest.mark.parametrize("refunded_pence", [-1, 101, True])
def test_reconstructed_refund_total_stays_within_order_total(refunded_pence: int) -> None:
    # Arrange
    reconstruct = partial(
        Order,
        1,
        7,
        (OrderLine("book", 1, 100),),
        100,
        date(2026, 7, 13),
        refunded_pence=refunded_pence,
    )

    # Act
    caught = _capture(InvalidOrderSnapshotError, reconstruct)

    # Assert
    assert caught.context["refunded_pence"] == refunded_pence


@pytest.mark.parametrize(
    ("refunded_pence", "status"),
    [
        (50, OrderStatus.PLACED),
        (0, OrderStatus.PARTIALLY_REFUNDED),
        (50, OrderStatus.REFUNDED),
        (50, OrderStatus.CANCELLED),
    ],
)
def test_reconstructed_status_must_match_refund_total(
    refunded_pence: int, status: OrderStatus
) -> None:
    # Arrange
    reconstruct = partial(
        Order,
        1,
        7,
        (OrderLine("book", 1, 100),),
        100,
        date(2026, 7, 13),
        refunded_pence=refunded_pence,
        status=status,
    )

    # Act
    caught = _capture(InvalidOrderSnapshotError, reconstruct)

    # Assert
    assert caught.context["status"] is status
