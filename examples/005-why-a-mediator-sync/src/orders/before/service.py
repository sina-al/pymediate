"""The order feature implemented as one service class.

Every operation is a typed method. The class also exposes an optional string-based
`dispatch` method for dynamic callers. That method demonstrates properties of string
routing; those properties do not apply to callers that use the typed methods directly.

This is the synchronous mirror of `examples/005-why-a-mediator/`.
"""

from typing import Any

from orders.domain import (
    AuditLog,
    ExportResult,
    InventoryService,
    Mailer,
    Order,
    OrderStore,
    PaymentGateway,
)

PRICE = 10  # flat price per item, for the demo


class OrderService:
    """One class that does everything the orders feature does."""

    def __init__(
        self,
        store: OrderStore,
        payments: PaymentGateway,
        mailer: Mailer,
        inventory: InventoryService,
        audit: AuditLog,
    ) -> None:
        # Construction requires every collaborator, including for callers that use a
        # method with fewer dependencies.
        self._store = store
        self._payments = payments
        self._mailer = mailer
        self._inventory = inventory
        self._audit = audit

    def place_order(self, customer_id: int, items: list[str]) -> Order:
        self._audit.record("place_order")  # repeated audit call, 1 of 3
        self._inventory.reserve(items)
        order = self._store.save(customer_id, items)
        self._payments.charge(order.order_id, PRICE * len(items))
        self._mailer.send(f"customer-{customer_id}", f"Order {order.order_id} placed")
        return order

    def cancel_order(self, order_id: int) -> Order:
        self._audit.record("cancel_order")  # copy 2 of 3
        order = self._store.get(order_id)
        order.status = "cancelled"
        return order

    def refund(self, order_id: int, amount: int) -> Order:
        # This method omits the audit call repeated by the other operations.
        order = self._store.get(order_id)
        self._payments.refund(order_id, amount)
        order.status = "refunded"
        return order

    def export_orders(self, customer_id: int, fmt: str = "csv") -> ExportResult:
        self._audit.record("export_orders")  # copy 3 of 3
        rows = [o for o in self._store.orders.values() if o.customer_id == customer_id]
        return ExportResult(url=f"/exports/{customer_id}.{fmt}", rows=len(rows))

    def dispatch(self, action: str, payload: dict[str, Any]) -> Any:
        """Route an action string to a method.

        This optional dynamic entry point accepts any `str`, so a misspelled action fails
        at runtime. Its branches return different types, so its return annotation is `Any`.
        The typed methods above retain their specific parameter and return types.
        """
        if action == "place_order":
            return self.place_order(payload["customer_id"], payload["items"])
        if action == "cancel_order":
            return self.cancel_order(payload["order_id"])
        if action == "refund":
            return self.refund(payload["order_id"], payload["amount"])
        if action == "export_orders":
            return self.export_orders(payload["customer_id"], payload.get("fmt", "csv"))
        raise ValueError(f"unknown action: {action!r}")
