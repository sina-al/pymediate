"""The core's domain errors — adapters translate these at the boundary."""


class ShopError(Exception):
    """Base class for every error the core raises on purpose."""


class CustomerNotFoundError(ShopError):
    """Raised when a request references a customer that doesn't exist."""

    def __init__(self, customer_id: str) -> None:
        super().__init__(f"No customer with id {customer_id}")
        self.customer_id = customer_id


class OrderNotFoundError(ShopError):
    """Raised when a request references an order that doesn't exist."""

    def __init__(self, order_id: str) -> None:
        super().__init__(f"No order with id {order_id}")
        self.order_id = order_id


class InvalidOrderStateError(ShopError):
    """Raised when an order can't perform the requested transition."""

    def __init__(self, order_id: str, status: str, action: str) -> None:
        super().__init__(f"Cannot {action} order {order_id}: status is {status}")
        self.order_id = order_id
        self.status = status
        self.action = action
