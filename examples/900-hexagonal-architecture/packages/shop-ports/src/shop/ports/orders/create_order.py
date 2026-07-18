"""Narrow outbound ports required only by the create-order use case."""

from datetime import date
from typing import Protocol, runtime_checkable

from shop.domain.entities.orders import Order, OrderItem, Product
from shop.ports.outbox import OutboxWriter


@runtime_checkable
class ProductCatalogue(Protocol):
    """Look up product prices without exposing catalogue infrastructure."""

    async def get_product(self, sku: str) -> Product: ...


@runtime_checkable
class CreateOrderClock(Protocol):
    """Supply the business date without importing ambient system time."""

    def today(self) -> date: ...


@runtime_checkable
class CreateOrderDbGateway(OutboxWriter, Protocol):
    """Expose only the database operations needed to create an order."""

    async def next_order_identity(self) -> int: ...
    async def insert_order(self, order: Order) -> None: ...


@runtime_checkable
class CreateOrderInventory(Protocol):
    """Reserve the products requested by a new order."""

    async def reserve(self, items: tuple[OrderItem, ...]) -> None: ...
    async def release(self, items: tuple[OrderItem, ...]) -> None: ...


@runtime_checkable
class CreateOrderPaymentGateway(Protocol):
    """Charge for a newly placed order."""

    async def charge(self, order_id: int, amount_pence: int) -> None: ...
    async def refund(self, order_id: int, amount_pence: int) -> None: ...
