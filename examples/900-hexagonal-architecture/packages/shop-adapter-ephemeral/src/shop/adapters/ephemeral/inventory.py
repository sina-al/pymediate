"""Local inventory adapter."""

from dataclasses import dataclass, field

from shop.domain.entities.orders import OrderItem
from shop.ports.orders.cancel_order import CancelOrderInventory
from shop.ports.orders.create_order import CreateOrderInventory


@dataclass
class EphemeralInventory(CreateOrderInventory, CancelOrderInventory):
    """Record reservations and releases in place of a warehouse API."""

    reservations: list[tuple[OrderItem, ...]] = field(default_factory=list)
    releases: list[tuple[OrderItem, ...]] = field(default_factory=list)

    async def reserve(self, items: tuple[OrderItem, ...]) -> None:
        self.reservations.append(items)

    async def release(self, items: tuple[OrderItem, ...]) -> None:
        self.releases.append(items)
