"""Register the order handlers and successful-request audit behavior.

`AuditBehavior` records requests after their handlers return successfully. Individual
handlers in ``operations.py`` therefore do not contain audit calls.

This is the synchronous mirror of `examples/005-why-a-mediator/`, built on ``pymediate.sync``.
"""

from collections.abc import Callable
from typing import Any

from pymediate.sync import Mediator, PipelineBehavior, Request, Services

from orders.after.operations import (
    CancelOrderHandler,
    ExportOrdersHandler,
    PlaceOrderHandler,
    RefundOrderHandler,
)
from orders.domain import AuditLog, InventoryService, Mailer, OrderStore, PaymentGateway


class AuditBehavior(PipelineBehavior[Request[Any]]):
    """Record each request after its handler returns successfully.

    The ``Request[Any]`` type parameter applies the behavior to every request type.
    Exceptions propagate before the audit entry is written.
    """

    def __init__(self, audit: AuditLog) -> None:
        self._audit = audit

    def __call__(self, request: Request[Any], next: Callable[[], Any]) -> Any:
        result = next()
        self._audit.record(type(request).__name__)
        return result


def build_mediator(
    store: OrderStore | None = None,
    payments: PaymentGateway | None = None,
    mailer: Mailer | None = None,
    inventory: InventoryService | None = None,
    audit: AuditLog | None = None,
) -> Mediator:
    """Wire a mediator: one handler instance per request, plus the audit behavior.

    Every collaborator defaults to a fresh in-memory implementation, so `build_mediator()` with no
    arguments is a complete, working application. Pass your own to observe them in a test.
    """
    store = store if store is not None else OrderStore()
    payments = payments if payments is not None else PaymentGateway()
    mailer = mailer if mailer is not None else Mailer()
    inventory = inventory if inventory is not None else InventoryService()
    audit = audit if audit is not None else AuditLog()

    services = Services()
    services.add(AuditBehavior(audit))
    services.add(PlaceOrderHandler(store, payments, mailer, inventory))
    services.add(CancelOrderHandler(store))
    services.add(RefundOrderHandler(store, payments))
    services.add(ExportOrdersHandler(store))
    return Mediator(services.provider(), behaviors=[AuditBehavior])
