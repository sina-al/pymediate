"""Cross-cutting concerns: one home, wrapping every request."""

from collections.abc import Callable
from typing import Any

from pymediate import PipelineBehavior, Request

from shop_ports.audit import AuditLog


class AuditTrail(PipelineBehavior[Request[Any]]):
    """Records every dispatched request in the audit log.

    The copy-pasted `audit_log.record(...)` line from the article's service methods,
    written exactly once.
    """

    def __init__(self, audit: AuditLog) -> None:
        self._audit = audit

    def __call__(self, request: Request[Any], next: Callable[[], Any]) -> Any:
        self._audit.record(type(request).__name__)
        return next()
