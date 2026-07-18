"""System clock adapter."""

from datetime import UTC, date, datetime

from shop.ports.orders.create_order import CreateOrderClock


class SystemClock(CreateOrderClock):
    """Supply the current UTC business date."""

    def today(self) -> date:
        return datetime.now(UTC).date()
