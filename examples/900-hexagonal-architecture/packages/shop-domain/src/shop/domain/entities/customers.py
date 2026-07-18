"""Customer entities kept separate from the orders domain model."""

from dataclasses import dataclass, replace

from shop.domain.errors import InvalidIdentifierError
from shop.domain.errors.customers import InvalidStoreCreditBalanceError, InvalidStoreCreditError


@dataclass(frozen=True)
class CustomerAccount:
    """A customer's store-credit balance."""

    customer_id: int
    store_credit_pence: int = 0

    def __post_init__(self) -> None:
        if (
            not isinstance(self.customer_id, int)
            or isinstance(self.customer_id, bool)
            or self.customer_id < 1
        ):
            raise InvalidIdentifierError("customer_id", self.customer_id)
        if (
            not isinstance(self.store_credit_pence, int)
            or isinstance(self.store_credit_pence, bool)
            or self.store_credit_pence < 0
        ):
            raise InvalidStoreCreditBalanceError(self.store_credit_pence)

    @classmethod
    def open(cls, customer_id: int) -> "CustomerAccount":
        """Open a new account with an immutable zero balance."""
        return cls(customer_id=customer_id)

    def add_store_credit(self, amount_pence: int) -> "CustomerAccount":
        """Return the account after crediting a positive refund amount."""
        if not isinstance(amount_pence, int) or isinstance(amount_pence, bool) or amount_pence < 1:
            raise InvalidStoreCreditError(amount_pence)
        return replace(self, store_credit_pence=self.store_credit_pence + amount_pence)
