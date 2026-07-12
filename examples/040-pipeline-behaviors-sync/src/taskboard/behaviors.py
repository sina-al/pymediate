"""The pipeline: four cross-cutting concerns, each with exactly one home.

This is the whole point of the example. Logging, authorization, caching, and
transactions are concerns that would otherwise be copy-pasted into every handler.
Here each lives in one ``PipelineBehavior``, and **its type parameter decides which
requests it wraps** — no registration list, no ``if isinstance`` ladder in a handler:

- ``LoggingBehavior(PipelineBehavior[Request])`` — *universal*: wraps every request.
- ``AuthorizationBehavior(PipelineBehavior[Command])`` — *selective*: only commands.
- ``CachingBehavior(PipelineBehavior[Query])`` — *selective*, and it *short-circuits*:
  on a cache hit it returns without calling ``next()``, so the handler never runs.
- ``TransactionBehavior(PipelineBehavior[Command])`` — *selective*: only commands.

Registration order (see ``app.build_mediator``) is execution order: the first behavior
registered is the outermost wrapper. Every behavior appends to a shared ``trace`` list so
the ordering and the short-circuit are observable in the demo and asserted in the tests.
This is the synchronous mirror of ``examples/040-pipeline-behaviors/behaviors.py`` — same
structure, plain ``next()`` instead of ``await next()``.
"""

from collections.abc import Callable
from typing import Any

from pymediate.sync import PipelineBehavior, Request

from .domain import AccessDeniedError, Command, FakeCache, Principal, Query, TaskStore


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
        self._trace.append(f"authz {name}")
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
    """Run each command inside a transaction. Selective — commands only, innermost.

    Registered last, so it sits closest to the handler: it opens the transaction just
    before the handler runs and commits just after, or rolls back if the handler raises.
    The ``begin``/``commit``/``rollback`` markers stand in for ``with session.begin()``
    against a real database.
    """

    def __init__(self, store: TaskStore, trace: list[str]) -> None:
        self._store = store
        self._trace = trace

    def __call__(self, request: Command, next: Callable[[], Any]) -> Any:
        self._trace.append("tx:begin")
        try:
            response = next()
        except Exception:
            self._trace.append("tx:rollback")
            raise
        self._trace.append("tx:commit")
        return response
