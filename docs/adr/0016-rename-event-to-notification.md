# ADR 0016: Rename `Event`/`EventHandler` to `Notification`/`NotificationHandler`

**Status:** Proposed
**Date:** 2026-07-19
**Author:** Claude
**Reviewers:** @sina-al

## Context

ADR 0005 introduced typed publish/subscribe under the name `Event`, and ADR 0006
renamed `Handler` → `RequestHandler` to give the two dispatch kinds a coherent family.
That family is now `RequestHandler` for the one-handler/typed-response side and
`EventHandler` for the fire-and-notify side, with a base `Event`, an `event` parameter,
`InvalidEventTypeError`, and the `event.py` modules carrying the concept.

The remaining rough edge is the word itself. "Event" is one of the most overloaded terms
in application code: most projects already run an event loop, an event bus, domain
events, or framework UI events, and a publishable base class named `Event` sits awkwardly
next to all of them. At every call site the user has to overload a word they have already
spent on something else.

```python
from pymediate import Event, EventHandler

class OrderPlaced(Event): ...                      # which "event"?
class SendConfirmation(EventHandler[OrderPlaced]):
    async def __call__(self, event: OrderPlaced) -> None: ...
```

`Event`, `EventHandler`, and `InvalidEventTypeError` are all in `__init__.py`'s `__all__` —
surfaces the versioning policy and CI flag as breaking-change points — hence this ADR.

## Proposed Solution(s)

### Option A — rename to `Notification`/`NotificationHandler`, clean break (RECOMMENDED)

Rename the concept to `Notification` / `NotificationHandler` across both the async
(`pymediate`) and sync (`pymediate.sync`) mirrors, matching MediatR's
`INotification` / `INotificationHandler` — the same naming ancestor ADR 0006 cited when it
renamed `Handler` → `RequestHandler`. `InvalidEventTypeError` moves with the concept to
`InvalidNotificationTypeError`. The dispatch verb stays `Mediator.publish(notification)` —
MediatR publishes notifications too, so the verb already fits. No deprecation alias: the
old names disappear from `__all__` and the package entirely.

```python
from pymediate import Notification, NotificationHandler

class OrderPlaced(Notification): ...
class SendConfirmation(NotificationHandler[OrderPlaced]):
    async def __call__(self, notification: OrderPlaced) -> None: ...
```

Pros:

- `Notification` names what the library actually does — fire-and-notify to zero-or-more
  subscribers — without claiming a word the user has already spent.
- Completes the MediatR alignment ADR 0006 started (`IRequestHandler` /
  `INotificationHandler`) rather than opening a new naming debate.
- Cheapest now: under ZeroVer this is a minor bump, and the user base is at its smallest
  it will ever be. Every release shipping more docs, examples, and user code on the
  `Event` name raises the future cost.

Cons:

- Every consumer must rename imports and base classes (mechanical, but real), with no
  runtime warning window — a clean break.
- Every internal surface quoting the old name must move in lockstep.

### Option B — rename with a deprecated `Event`/`EventHandler` alias

Keep the old names importable for one minor via PEP 562 `__getattr__` emitting a
`DeprecationWarning`, as ADR 0006 first proposed for `Handler`.

Pros: existing code keeps running for one release with an actionable warning.
Cons: ADR 0006's own amendment judged a deprecation window "over the top" for this
near-zero user base and removed the shims immediately; carrying one here would contradict
that precedent for no proportionate benefit.

### Option C — keep `Event`

Accept `Event` as the permanent name.

Pros: no migration.
Cons: the collision with the user's own event vocabulary is permanent, and the cheapest
moment to fix it (now) is spent.

## Decision

Option A — rename to `Notification`/`NotificationHandler`, clean break, no alias.

- `Notification`/`NotificationHandler` become the canonical names in `pymediate` and
  `pymediate.sync` (structural mirrors — they change together). `Event`, `EventHandler`,
  and `InvalidEventTypeError` are removed from `__all__` and the package entirely; no
  `__getattr__` shim, no `Event = Notification` assignment. This follows ADR 0006's
  amendment (near-zero user base, no deprecation window worth carrying).
- `InvalidEventTypeError` → `InvalidNotificationTypeError`. Unlike the handler-umbrella
  errors ADR 0006 deliberately left alone (`HandlerNotFoundError`,
  `HandlerAlreadyRegisteredError`, `InvalidHandlerSignatureError` — accurate across both
  dispatch kinds), this error names the `Event` concept specifically, so it moves with the
  base class to keep the public vocabulary consistent.
- `Mediator.publish()` keeps its name; only the parameter changes (`event` →
  `notification`). No other `Mediator` method changes.
- Module files are renamed `event.py` → `notification.py` (public, `_internal`, and sync
  mirror) for concept coherence. Module paths are not the public contract (`__all__` is),
  so this is safe — the same grouping ADR 0006 used.
- Internal vocabulary moves in lockstep: `EventHandlerBaseMixin` →
  `NotificationHandlerBaseMixin`, the registry's event routing (`register_event_handler`,
  `get_event_handler_classes`, `has_event_handlers`, `get_all_event_types`,
  `_EVENT_HANDLER_REGISTRY`, `_event_lock`, `_event_type`, `get_event_type`,
  `_resolve_event_handlers`, the `kind="event"` validation tag, and the
  `event_handler_count` stat). `_internal/` has no back-compat surface.
- Versioning: minor (`0.X.0`) — removed/changed names in `__all__` are a breaking
  public-API change under the versioning policy.

## Consequences

### Positive

- The public vocabulary states what the concept is — a `Notification` published to zero
  or more `NotificationHandler`s — without colliding with the user's existing event
  systems.
- Completes the MediatR-aligned family (`RequestHandler` / `NotificationHandler`) ADR 0006
  began.

### Negative

- Every consumer must rename imports and base classes; there is no deprecation window.
- Every internal surface quoting the old name moves in one change: source docstrings and
  their runnable examples, tests, the typing-snippet corpus and its pinned diagnostics in
  `tests/typing/expectations.py` (checker messages quote the class/error names), the docs
  site (including the `api/event*` page slugs), and the generated
  `.claude/context/api-signatures.md`. A stray old-name reference in checker expectations
  fails CI — the safety net working.
- The `errors/` typing snippets stay deliberately invalid; they are renamed and their
  pinned diagnostics updated, but must remain red under both checkers.

### Deferred

- The `examples/` curriculum entries that publish events (and their sync mirrors) are
  **not** touched here. Examples run against the released PyPI package, so they are a
  post-release follow-up owned by the `example` skill once a release carrying the rename
  ships.

## Migration Path

```python
# before
from pymediate import Event, EventHandler

class OrderPlaced(Event): ...
class SendConfirmation(EventHandler[OrderPlaced]):
    async def __call__(self, event: OrderPlaced) -> None: ...

# after
from pymediate import Notification, NotificationHandler

class OrderPlaced(Notification): ...
class SendConfirmation(NotificationHandler[OrderPlaced]):
    async def __call__(self, notification: OrderPlaced) -> None: ...
```

The same substitution applies to `pymediate.sync`, and `InvalidEventTypeError` becomes
`InvalidNotificationTypeError`. `Mediator.publish(notification)` is unchanged. The rename
ships as a minor bump (a changed name in `__all__`, per the versioning policy).
