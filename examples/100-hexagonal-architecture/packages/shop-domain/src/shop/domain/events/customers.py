"""Business facts emitted by the customers domain."""

from dataclasses import dataclass
from typing import ClassVar

from shop.domain.events.base import AggregateRef, AggregateType, EventPayload


@dataclass(frozen=True)
class CustomerAccountOpenedEvent:
    """Record that a new customer account became available."""

    customer_id: int

    event_name: ClassVar[str] = "customers.account-opened"
    schema_version: ClassVar[int] = 1

    @property
    def aggregate(self) -> AggregateRef:
        return AggregateRef(AggregateType.CUSTOMER, str(self.customer_id))

    def payload(self) -> EventPayload:
        """Return the durable primitive payload for this event."""
        return {"customer_id": self.customer_id}


@dataclass(frozen=True)
class StoreCreditAdjustedEvent:
    """Record a successful increase to a customer's store credit."""

    customer_id: int
    amount_pence: int
    store_credit_pence: int

    event_name: ClassVar[str] = "customers.store-credit-adjusted"
    schema_version: ClassVar[int] = 1

    @property
    def aggregate(self) -> AggregateRef:
        return AggregateRef(AggregateType.CUSTOMER, str(self.customer_id))

    def payload(self) -> EventPayload:
        """Return the durable primitive payload for this event."""
        return {
            "customer_id": self.customer_id,
            "amount_pence": self.amount_pence,
            "store_credit_pence": self.store_credit_pence,
        }


@dataclass(frozen=True)
class CustomerAccountClosedEvent:
    """Record that a customer account was successfully closed."""

    customer_id: int

    event_name: ClassVar[str] = "customers.account-closed"
    schema_version: ClassVar[int] = 1

    @property
    def aggregate(self) -> AggregateRef:
        return AggregateRef(AggregateType.CUSTOMER, str(self.customer_id))

    def payload(self) -> EventPayload:
        """Return the durable primitive payload for this event."""
        return {"customer_id": self.customer_id}
