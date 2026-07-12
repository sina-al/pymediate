"""Assemble the mediator: the one place that knows every handler and the audit seam.

This is the destination the god service never had — a single file entitled to know
everything, so no caller has to. It also hosts the cross-cutting concern: `AuditBehavior`
wraps every request once, which is why no operation in ``operations.py`` repeats it.
"""

from collections.abc import Awaitable, Callable
from typing import Any

from pymediate import Mediator, PipelineBehavior, Request, Services

from orders.after.operations import (
    CancelOrderHandler,
    ExportOrdersHandler,
    PlaceOrderHandler,
    RefundOrderHandler,
)
from orders.domain import AuditLog, InventoryService, Mailer, OrderStore, PaymentGateway


class AuditBehavior(PipelineBehavior[Request[Any]]):
    """Records every request that flows through the mediator — one home for auditing.

    The ``Request[Any]`` type parameter makes it apply to *every* operation. A new handler
    is audited the moment it's registered; there is no per-method line to copy, so there is
    none to forget. This is the god service's Pain #3, closed for good.
    """

    def __init__(self, audit: AuditLog) -> None:
        self._audit = audit

    async def __call__(self, request: Request[Any], next: Callable[[], Awaitable[Any]]) -> Any:
        result = await next()
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

    Every collaborator defaults to a fresh in-memory fake, so `build_mediator()` with no
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
    return Mediator(services.provider())
