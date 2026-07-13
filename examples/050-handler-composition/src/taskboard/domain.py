"""The orders domain: data and the fake collaborators each sub-operation owns.

Nothing here knows about composition. Each collaborator is a dull in-memory stand-in for
real infrastructure (a warehouse, a shipping-rates API, an order database). The
``await asyncio.sleep(...)`` calls stand in for real I/O — they're what makes the
concurrency in the async orchestrator observable in `app.py` and the tests.
"""

import asyncio
from dataclasses import dataclass, field


@dataclass
class Order:
    """A placed order, with the reservation and shipping quote that produced it."""

    order_id: int
    items: list[str]
    reservation_id: str
    shipping_cost: int


@dataclass
class StockReservation:
    """Proof that a warehouse set aside the requested items."""

    reservation_id: str


@dataclass
class ShippingQuote:
    """A carrier's price to ship the requested items."""

    cost: int


# ---- Collaborators: fakes standing in for real infrastructure ----


@dataclass
class Warehouse:
    """Reserves stock (a stand-in for a warehouse service). Records every reservation."""

    trace: list[str] = field(default_factory=list)
    reserved: list[list[str]] = field(default_factory=list)
    _next: int = 1

    async def reserve(self, items: list[str]) -> StockReservation:
        """Reserve stock for the items, after a short simulated round-trip."""
        self.trace.append("reserve:start")
        await asyncio.sleep(0.05)  # stand-in for a real warehouse call
        self.reserved.append(list(items))
        reservation = StockReservation(reservation_id=f"resv-{self._next}")
        self._next += 1
        self.trace.append("reserve:done")
        return reservation


@dataclass
class ShippingRates:
    """Quotes shipping (a stand-in for a carrier-rates API). Records every quote."""

    trace: list[str] = field(default_factory=list)
    quoted: list[list[str]] = field(default_factory=list)

    async def quote(self, items: list[str]) -> ShippingQuote:
        """Quote shipping for the items, after a short simulated round-trip."""
        self.trace.append("quote:start")
        await asyncio.sleep(0.05)  # stand-in for a real rates API call
        self.quoted.append(list(items))
        self.trace.append("quote:done")
        return ShippingQuote(cost=5 * len(items))


@dataclass
class OrderStore:
    """In-memory order storage (a stand-in for a database)."""

    orders: dict[int, Order] = field(default_factory=dict)
    next_id: int = 1

    def save(self, items: list[str], reservation_id: str, shipping_cost: int) -> Order:
        """Persist a new order and return it."""
        order = Order(
            order_id=self.next_id,
            items=list(items),
            reservation_id=reservation_id,
            shipping_cost=shipping_cost,
        )
        self.orders[order.order_id] = order
        self.next_id += 1
        return order
