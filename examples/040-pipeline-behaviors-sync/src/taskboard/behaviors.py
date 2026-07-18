"""Four behaviors for logging, authorization, caching, and a transaction boundary.

Each behavior's type parameter selects the requests it wraps:

- ``LoggingBehavior(PipelineBehavior[Request])`` — *universal*: wraps every request.
- ``AuthorizationBehavior(PipelineBehavior[Command])`` — *selective*: only commands.
- ``CachingBehavior(PipelineBehavior[Query])`` — *selective*, and it *short-circuits*:
  on a cache hit it returns without calling ``next()``, so the handler never runs.
- ``TransactionBehavior(PipelineBehavior[Command])`` — *selective*: traces where a real
  transaction manager would wrap commands.

Registration order (see ``app.build_mediator``) is execution order: the first behavior
registered is the outermost wrapper. Every behavior appends to a shared ``trace`` list so
the ordering and the short-circuit are observable in the demo and asserted in the tests.
This is the synchronous mirror of ``examples/040-pipeline-behaviors/behaviors.py`` — same
structure, plain ``next()`` instead of ``await next()``.
"""

from collections.abc import Callable
from typing import Any

from pymediate.sync import PipelineBehavior, Request

from .domain import AccessDeniedError, Command, FakeCache, Principal, Query


class LoggingBehavior(PipelineBehavior[Request]):
    """Log the entry and exit of every request. Universal — ``[Request]`` matches all.

    Registered outermost, so its ``log:exit`` runs even when an inner behavior
    short-circuits or raises — logging should see everything.
    """

    def __init__(self, trace: list[str]) -> None:
        self._trace = trace

    def __call__(self, request: Request[Any], next: Callable[[], Any]) -> Any:
        name = type(request).__name__
        self._trace.append(f"log:enter {name}")
        try:
            return next()
        finally:
            self._trace.append(f"log:exit {name}")


class AuthorizationBehavior(PipelineBehavior[Command]):
    """Reject commands the principal isn't allowed to run. Selective — commands only.

    Because the type parameter is ``Command``, read-only ``Query`` requests never reach
    this check. The ``Principal`` is a constructor dependency — the kind of swappable
    collaborator a plain decorator can't carry cleanly.
    """

    def __init__(self, principal: Principal, trace: list[str]) -> None:
        self._principal = principal
        self._trace = trace

    def __call__(self, request: Command, next: Callable[[], Any]) -> Any:
        name = type(request).__name__
        if not self._principal.can_write:
            raise AccessDeniedError(f"{self._principal.name} may not run {name}")
        self._trace.append(f"authorization {name}")
        return next()


class CachingBehavior(PipelineBehavior[Query]):
    """Serve reads from a cache, short-circuiting the handler on a hit. Selective — queries.

    ``should_apply`` adds a *runtime* condition on top of the type routing: a query can
    opt out per request via ``cacheable=False`` (see ``ListOpenTasks``), and then this
    behavior is skipped entirely. On a cache hit ``next()`` is never called, so the
    handler — and any behavior nested inside this one — never runs. That skip is the
    feature; forgetting to call ``next()`` anywhere else would be a bug.
    """

    def __init__(self, cache: FakeCache, trace: list[str]) -> None:
        self._cache = cache
        self._trace = trace

    @classmethod
    def should_apply(cls, request: Request[Any]) -> bool:
        """Wrap a query only when it hasn't opted out of caching at runtime."""
        return isinstance(request, Query) and request.cacheable

    def __call__(self, request: Query, next: Callable[[], Any]) -> Any:
        name = type(request).__name__
        key = repr(request)
        cached = self._cache.get(key)
        if cached is not None:
            self._trace.append(f"cache:hit {name}")
            return cached  # short-circuit: next() is never called, the handler is skipped
        self._trace.append(f"cache:miss {name}")
        response = next()
        self._cache.set(key, response)
        return response


class TransactionBehavior(PipelineBehavior[Command]):
    """Trace the boundary where a transaction manager would wrap each command.

    This example does not implement transaction state or rollback. The trace records entry,
    successful exit, or an error around the handler.
    """

    def __init__(self, trace: list[str]) -> None:
        self._trace = trace

    def __call__(self, request: Command, next: Callable[[], Any]) -> Any:
        self._trace.append("transaction:enter")
        try:
            response = next()
        except Exception:
            self._trace.append("transaction:error")
            raise
        self._trace.append("transaction:exit")
        return response
