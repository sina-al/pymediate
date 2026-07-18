"""Entities and value objects that keep the shop's business rules in the domain."""

from dataclasses import dataclass, replace
from datetime import date
from enum import StrEnum

from shop.domain.errors import InvalidIdentifierError
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


class OrderStatus(StrEnum):
    """Business states relevant to order operations."""

    PLACED = "placed"
    PARTIALLY_REFUNDED = "partially-refunded"
    REFUNDED = "refunded"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class Product:
    """A product the shop can sell."""

    sku: str
    price_pence: int

    def __post_init__(self) -> None:
        _validate_sku(self.sku)
        _validate_price(self.price_pence)


@dataclass(frozen=True)
class OrderItem:
    """A customer's request for a quantity of one product."""

    sku: str
    quantity: int

    def __post_init__(self) -> None:
        _validate_sku(self.sku)
        _validate_quantity(self.quantity)


@dataclass(frozen=True)
class OrderLine:
    """A priced item captured on an order."""

    sku: str
    quantity: int
    unit_price_pence: int

    def __post_init__(self) -> None:
        _validate_sku(self.sku)
        _validate_quantity(self.quantity)
        _validate_price(self.unit_price_pence)

    @property
    def subtotal_pence(self) -> int:
        """Return this line's quantity-adjusted price."""
        return self.quantity * self.unit_price_pence


@dataclass(frozen=True)
class Order:
    """A placed order that owns its total and refund invariants."""

    order_id: int
    customer_id: int
    lines: tuple[OrderLine, ...]
    total_pence: int
    placed_on: date
    refunded_pence: int = 0
    status: OrderStatus = OrderStatus.PLACED

    def __post_init__(self) -> None:
        _validate_identifier("order_id", self.order_id)
        _validate_identifier("customer_id", self.customer_id)
        if not self.lines:
            raise EmptyOrderError()
        calculated_pence = sum(line.subtotal_pence for line in self.lines)
        if (
            not isinstance(self.total_pence, int)
            or isinstance(self.total_pence, bool)
            or self.total_pence != calculated_pence
        ):
            raise InvalidOrderTotalError(self.total_pence, calculated_pence)
        if type(self.placed_on) is not date:
            raise InvalidOrderSnapshotError("placed_on must be a date", placed_on=self.placed_on)
        if (
            not isinstance(self.refunded_pence, int)
            or isinstance(self.refunded_pence, bool)
            or not 0 <= self.refunded_pence <= self.total_pence
        ):
            raise InvalidOrderSnapshotError(
                "refunded total is outside the order total",
                refunded_pence=self.refunded_pence,
                total_pence=self.total_pence,
            )
        expected_refund = {
            OrderStatus.PLACED: self.refunded_pence == 0,
            OrderStatus.CANCELLED: self.refunded_pence == 0,
            OrderStatus.PARTIALLY_REFUNDED: 0 < self.refunded_pence < self.total_pence,
            OrderStatus.REFUNDED: self.refunded_pence == self.total_pence,
        }
        if not isinstance(self.status, OrderStatus) or not expected_refund[self.status]:
            raise InvalidOrderSnapshotError(
                "status does not match the refunded total",
                status=self.status,
                refunded_pence=self.refunded_pence,
                total_pence=self.total_pence,
            )

    @classmethod
    def place(
        cls,
        order_id: int,
        customer_id: int,
        lines: tuple[OrderLine, ...],
        placed_on: date,
    ) -> "Order":
        """Place an order and derive its total from priced lines."""
        if not lines:
            raise EmptyOrderError()
        total_pence = sum(line.subtotal_pence for line in lines)
        return cls(order_id, customer_id, lines, total_pence, placed_on)

    def refund(self, amount_pence: int) -> "Order":
        """Return the order after a valid partial or complete refund."""
        refundable = self.total_pence - self.refunded_pence
        if not isinstance(amount_pence, int) or isinstance(amount_pence, bool) or amount_pence < 1:
            raise ExcessiveRefundError(amount_pence, refundable)
        refunded = self.refunded_pence + amount_pence
        if refunded > self.total_pence:
            raise ExcessiveRefundError(amount_pence, refundable)
        if self.status is OrderStatus.CANCELLED:
            raise InvalidOrderStateError("refunded", self.status.value)
        status = (
            OrderStatus.REFUNDED if refunded == self.total_pence else OrderStatus.PARTIALLY_REFUNDED
        )
        return replace(self, refunded_pence=refunded, status=status)

    def cancel(self) -> "Order":
        """Return a cancellable order in its terminal cancelled state."""
        if self.status is not OrderStatus.PLACED:
            raise InvalidOrderStateError("cancelled", self.status.value)
        return replace(self, status=OrderStatus.CANCELLED)


def _validate_identifier(kind: str, value: object) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise InvalidIdentifierError(kind, value)


def _validate_sku(sku: object) -> None:
    if not isinstance(sku, str) or not sku.strip():
        raise InvalidSkuError(sku)


def _validate_quantity(value: object) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise InvalidQuantityError(value)


def _validate_price(value: object) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise InvalidPriceError(value)
