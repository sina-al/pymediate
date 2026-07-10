"""Persistence ports on plain dicts."""

from dataclasses import replace

from shop_domain.customers import Customer
from shop_domain.orders import Order


class MemoryOrderRepository:
    """OrderRepository on a dict, insertion-ordered."""

    def __init__(self) -> None:
        self._orders: dict[str, Order] = {}

    def add(self, order: Order) -> None:
        self._orders[order.order_id] = order

    def get(self, order_id: str) -> Order | None:
        return self._orders.get(order_id)

    def update(self, order: Order) -> None:
        self._orders[order.order_id] = order

    def for_customer(self, customer_id: str) -> list[Order]:
        return [o for o in self._orders.values() if o.customer_id == customer_id]


class MemoryCustomerRepository:
    """CustomerRepository on a dict."""

    def __init__(self) -> None:
        self._customers: dict[str, Customer] = {}

    def add(self, customer: Customer) -> None:
        self._customers[customer.customer_id] = customer

    def get(self, customer_id: str) -> Customer | None:
        return self._customers.get(customer_id)

    def credit(self, customer_id: str, amount_cents: int) -> Customer | None:
        customer = self._customers.get(customer_id)
        if customer is None:
            return None
        updated = replace(customer, store_credit_cents=customer.store_credit_cents + amount_cents)
        self._customers[customer_id] = updated
        return updated
