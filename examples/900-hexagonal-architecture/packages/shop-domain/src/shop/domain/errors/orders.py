"""Business failures owned by the orders feature module."""

from shop.domain.errors import DomainError


class EmptyOrderError(DomainError):
    code = "empty-order"
    title = "Order has no lines"

    def __init__(self) -> None:
        super().__init__("An order needs at least one line.")


class InvalidQuantityError(DomainError):
    code = "invalid-quantity"
    title = "Invalid order quantity"

    def __init__(self, quantity: object) -> None:
        super().__init__("Quantities must be positive.", quantity=quantity)


class InvalidSkuError(DomainError, ValueError):
    code = "invalid-sku"
    title = "Invalid product SKU"

    def __init__(self, sku: object) -> None:
        super().__init__("A product SKU must not be empty.", sku=sku)


class InvalidPriceError(DomainError, ValueError):
    code = "invalid-price"
    title = "Invalid product price"

    def __init__(self, price_pence: object) -> None:
        super().__init__("A product price must be positive.", price_pence=price_pence)


class InvalidOrderTotalError(DomainError, ValueError):
    code = "invalid-order-total"
    title = "Invalid order total"

    def __init__(self, total_pence: object, calculated_pence: int) -> None:
        super().__init__(
            "An order total must equal the total derived from its lines.",
            total_pence=total_pence,
            calculated_pence=calculated_pence,
        )


class InvalidOrderSnapshotError(DomainError, ValueError):
    code = "invalid-order-snapshot"
    title = "Invalid order state"

    def __init__(self, reason: str, **context: object) -> None:
        super().__init__(f"The persisted order is inconsistent: {reason}.", **context)


class ProductNotFoundError(DomainError):
    code = "product-not-found"
    title = "Product not found"

    def __init__(self, sku: str) -> None:
        super().__init__(f"No product exists for SKU '{sku}'.", sku=sku)


class OrderNotFoundError(DomainError):
    code = "order-not-found"
    title = "Order not found"

    def __init__(self, order_id: int) -> None:
        super().__init__(f"Order {order_id} does not exist.", order_id=order_id)


class ExcessiveRefundError(DomainError):
    code = "excessive-refund"
    title = "Refund amount is invalid"

    def __init__(self, requested_pence: object, available_pence: int) -> None:
        super().__init__(
            "The refund must be positive and cannot exceed the unrefunded order total.",
            requested_pence=requested_pence,
            available_pence=available_pence,
        )


class InvalidOrderStateError(DomainError):
    code = "invalid-order-state"
    title = "Order state conflict"

    def __init__(self, operation: str, state: str) -> None:
        super().__init__(
            f"An order that is {state} cannot be {operation}.",
            operation=operation,
            state=state,
        )


class UnsupportedExportFormatError(DomainError):
    code = "unsupported-export-format"
    title = "Unsupported export format"

    def __init__(self, requested_format: str, supported_formats: tuple[str, ...]) -> None:
        super().__init__(
            f"Export format '{requested_format}' is not supported.",
            requested_format=requested_format,
            supported_formats=supported_formats,
        )
