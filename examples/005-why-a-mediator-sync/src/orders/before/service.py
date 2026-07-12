"""The order feature as one class — the shape most teams reach for first.

Every operation the application performs is a method here, and every collaborator any
operation could need is handed in once, at construction. It reads well; a new hire
understands it in a sitting. This is not a strawman — it's a competent, ordinary design,
the kind a good reviewer approves without comment.

It also degrades in four specific ways as it grows, and `tests/test_before.py` pins down
each one by *running* it. The `after/` package answers them one at a time.

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
        # Every collaborator any method might touch is handed in here — so anyone who
        # wants to construct an OrderService must supply all five, even to reach a method
        # that uses one of them. (Pain #4.)
        self._store = store
        self._payments = payments
        self._mailer = mailer
        self._inventory = inventory
        self._audit = audit

    def place_order(self, customer_id: int, items: list[str]) -> Order:
        self._audit.record("place_order")  # cross-cutting concern, copy 1 of 3 (Pain #3)
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
        # Added six months after the rest — and the `self._audit.record(...)` line that
        # opens every other method never made it in. Nothing catches the omission; the
        # audit trail just quietly stops recording refunds. (Pain #3, felt.)
        order = self._store.get(order_id)
        self._payments.refund(order_id, amount)
        order.status = "refunded"
        return order

    def export_orders(self, customer_id: int, fmt: str = "csv") -> ExportResult:
        self._audit.record("export_orders")  # copy 3 of 3
        rows = [o for o in self._store.orders.values() if o.customer_id == customer_id]
        return ExportResult(url=f"/exports/{customer_id}.{fmt}", rows=len(rows))

    def dispatch(self, action: str, payload: dict[str, Any]) -> Any:
        """Route an action name to a method — the string-keyed seam a god service grows.

        A web route, a worker, and a CLI all want to reach these operations without each
        importing the class, so a `dispatch(name, payload)` front door appears. Note the
        two costs baked into its signature. `action` is a bare `str`, so a mistyped name
        is invisible until it runs (Pain #1). And the branches return different types, so
        the only return type that fits is `Any` — which switches the type checker off at
        exactly the call site that most wants it (Pain #2).
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
