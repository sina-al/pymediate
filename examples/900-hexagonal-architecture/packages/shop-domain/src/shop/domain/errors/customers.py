"""Business failures owned by the customers feature module."""

from shop.domain.errors import DomainError


class InvalidStoreCreditError(DomainError, ValueError):
    code = "invalid-store-credit"
    title = "Invalid store credit"

    def __init__(self, amount_pence: int) -> None:
        super().__init__(
            "Store credit must be positive.",
            amount_pence=amount_pence,
        )


class InvalidStoreCreditBalanceError(DomainError, ValueError):
    code = "invalid-store-credit-balance"
    title = "Invalid store-credit balance"

    def __init__(self, balance_pence: int) -> None:
        super().__init__(
            "A store-credit balance cannot be negative.",
            balance_pence=balance_pence,
        )


class CustomerAlreadyExistsError(DomainError):
    code = "customer-already-exists"
    title = "Customer already exists"

    def __init__(self, customer_id: int) -> None:
        super().__init__(
            f"Customer {customer_id} already has an account.",
            customer_id=customer_id,
        )


class CustomerNotFoundError(DomainError):
    code = "customer-not-found"
    title = "Customer not found"

    def __init__(self, customer_id: int) -> None:
        super().__init__(
            f"Customer {customer_id} does not have an account.",
            customer_id=customer_id,
        )


class CustomerHasOpenOrdersError(DomainError):
    code = "customer-has-open-orders"
    title = "Customer account has open orders"

    def __init__(self, customer_id: int) -> None:
        super().__init__(
            f"Customer {customer_id} still has open orders.",
            customer_id=customer_id,
        )
