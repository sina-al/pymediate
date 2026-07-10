# ADR 0005: Typed event publishing (`mediator.publish`)

**Status:** Proposed
**Date:** 2026-07-10
**Author:** Claude
**Reviewers:** @sina-al

## Context

PyMediate's `send()` dispatches a request to **exactly one** handler and returns its typed
response. The complementary messaging shape — an event fanned out to **zero or more**
handlers, with no response — is the library's single biggest functional gap: a July 2026
source-level survey of the six most popular Python mediator libraries found five of six
have event publishing (issue #10, `.claude/context/mediator-survey.md`). Every surveyed
alternative's event API is type-erased or async-only; PyMediate's version should be typed
and validated end to end, in both the sync and async APIs, or it isn't worth shipping.

The design decisions below were locked with the maintainer on 2026-07-10 and recorded in
issue #10's Decisions table; this ADR records the design that satisfies them and the
alternatives rejected along the way.

## Proposed Solution(s)

### The API

```python
from dataclasses import dataclass
from pymediate import Event, EventHandler, Mediator, Services


@dataclass
class OrderPlaced(Event):
    order_id: int


class SendConfirmation(EventHandler[OrderPlaced]):
    def __call__(self, event: OrderPlaced) -> None: ...


class UpdateAnalytics(EventHandler[OrderPlaced]):
    def __call__(self, event: OrderPlaced) -> None: ...


services = Services()
services.add(SendConfirmation()).add(UpdateAnalytics())
mediator = Mediator(services.provider())

mediator.publish(OrderPlaced(order_id=42))  # both handlers run, in registration order
```

- **`Event`** — plain marker base class, mirroring `Request` structurally but with **no
  generic parameter**: events have no response type, so there is nothing to infer and
  nothing to register at definition time. `publish(event: Event) -> None` is typed to
  accept only `Event` instances, so passing a request (or anything else) is a static error.
- **`EventHandler[EventT: Event]`** — mirrors `Handler[RequestT]` with the same
  class-definition-time validation, reusing `_validate_call_signature()` (including PEP 563
  `get_type_hints()` resolution and ADR 0004's exact-annotation contract, which applies to
  events identically and for the same reason: dispatch is keyed by `type(event)`). Two
  event-specific differences:
  - the return annotation must be `None` — a non-`None` return annotation is an
    `InvalidHandlerSignatureError` that says so, rather than a confusing
    `ResponseTypeMismatchError` against `NoneType`;
  - the type parameter is **bound** (`EventT: Event`), so `EventHandler[NotAnEvent]` is a
    *static* error in mypy and basedpyright as well as a runtime `InvalidEventTypeError`.
    (`Handler[RequestT]` is unbound because `Request` subclasses must re-declare
    `Request[ResponseT]` and the interesting validation is the response lookup; events have
    no such lookup, so the bound is pure win.)
- **`InvalidEventTypeError`** — mirrors `InvalidRequestTypeError` for a type parameter that
  isn't an `Event` subclass. New name in `__all__`.
- **Registration** — a parallel N-allowed registry (`dict[type, list[type]]` in
  `_internal/registry.py`), *not* a relaxation of the request path:
  `HandlerAlreadyRegisteredError` and one-handler-per-request semantics are untouched.
- **`mediator.publish(event)`** — sync and async mirrors on the existing mediators.

### Locked semantics

**Zero handlers → silent no-op.** An event with no subscribers is a legitimate state;
erroring would couple publishers to subscriber existence, which is the coupling `publish`
exists to remove. (Contrast `send`, where a missing handler is `HandlerNotFoundError` —
a request needs its answer.)

**Resolution failures fail fast; execution failures aggregate.** `publish` resolves *all*
handler instances from the `ServiceProvider` before invoking any. A resolution failure
(`ServiceNotFoundError`) is a configuration bug and propagates immediately, before any
handler has run — so a misconfigured subscriber never causes partial delivery.

**One handler raising doesn't stop the others.** Every resolved handler runs; if any
raised, `publish` raises an `ExceptionGroup` (`except*`-compatible, Python 3.12+ being the
floor anyway) carrying every failure. Fail-fast was rejected because it makes delivery
depend on registration order — the handlers after the failing one silently miss the event,
which is the worst failure mode for notifications. A plain builtin `ExceptionGroup` is
used rather than a custom subclass: `except* SomeError` already selects by contained
exception type, and a bespoke group class would add a public name without adding a
capability.

**Invocation order is registration order** — the same order `ServiceProvider.get_all`
already contracts. Sync runs handlers sequentially in that order. Async schedules all
handlers concurrently via `asyncio.gather` (tasks are *created* in registration order,
then awaited together) — concurrency is the point of the aio mirror, and
`return_exceptions=True` gives exactly the run-everything-then-aggregate semantics chosen
above.

**`PipelineBehavior` does not wrap `publish` in v1.** Wrapping fan-out immediately raises
per-publish vs. per-handler questions (does a caching behavior short-circuit all
subscribers? does retry re-run the ones that succeeded?) and `should_apply` /
`PipelineBehavior[T]` are typed against `Request` (ADR 0002). Deferred deliberately;
revisiting it is its own ADR if demand materializes.

### Alternatives considered

- **`Event` as a parameterless alias of `Request[None]`** — would let events reuse the
  entire existing handler/registry path. Rejected: it collapses "exactly one handler,
  returns a response" and "zero or more handlers, returns nothing" into one registry,
  forcing the exactly-one invariant to grow a mode switch, and `send(event)` /
  `publish(request)` would both type-check while meaning nothing.
- **Fail-fast error propagation** — rejected above (delivery becomes registration-order
  dependent).
- **Sequential await in the async mirror** — rejected: it serializes independent I/O and
  still needs the aggregation machinery anyway; determinism of *completion* order is not
  something event handlers may assume in either variant (sync handlers should not depend
  on each other's effects — an ordering guarantee across subscribers is coupling by the
  back door).
- **`strict`/`require_handlers` flag on publish** — rejected for v1: YAGNI, and an
  application that wants the guarantee can assert `provider.has(SomeHandler)` at startup.

## Decision

Ship `Event`, `EventHandler[EventT: Event]`, `InvalidEventTypeError`, and
`mediator.publish()` (sync + aio) as described: N-allowed parallel registry, silent no-op
on zero handlers, resolve-all-then-run, run-all-then-`ExceptionGroup`, registration order,
`asyncio.gather` in aio, behaviors deferred. Adds three names to `__all__` → **minor**
bump per the ZeroVer policy.

## Consequences

### Positive

- Closes the headline feature gap with a version none of the surveyed alternatives have:
  typed (`publish` only accepts `Event`; handler signatures validated at import time,
  exact-annotation contract included) and symmetric across sync and async.
- Request semantics are completely untouched — separate base class, separate registry,
  separate error type. No behavior change for existing users.
- `ExceptionGroup` semantics make partial subscriber failure observable instead of
  silent or order-dependent.

### Negative

- New public surface to maintain across both mirrors (docstrings, API pages, typing
  snippets, examples).
- No pipeline behaviors on publish in v1 — cross-cutting concerns (logging, metrics)
  must live in the handlers or wait for a follow-up ADR.
- `asyncio.gather` means async handlers for one event run concurrently — handlers that
  mutate shared state must synchronize, and the docs must say so.

## Migration Path

No migration needed — purely additive. Existing `send()`/`Handler` code is unaffected.

## Open Questions

- Should a later version add hierarchy-aware publishing (a handler for a base event
  receives derived events)? Lean: no — same reasoning as ADR 0004; exact-type dispatch is
  the invariant everything else leans on. Revisit only with a concrete use case.
- `contrib` behaviors (#13) may eventually want publish-side hooks; that lands with the
  behaviors-on-publish ADR, not before.
