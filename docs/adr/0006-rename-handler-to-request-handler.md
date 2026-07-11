# ADR 0006: Rename `Handler` to `RequestHandler`

**Status:** Proposed
**Date:** 2026-07-11
**Author:** Claude
**Reviewers:** @sina-al

## Context

Until 0.3.0, `Handler` was the only handler in the library, and the bare name was
unambiguous. ADR 0005 introduced typed event publishing, and with it a second handler
kind — `EventHandler`. The two now sit side by side in the public API with asymmetric
names:

```python
from pymediate import Handler, EventHandler

class CreateUserHandler(Handler[CreateUser]): ...          # handles a *request*
class SendConfirmation(EventHandler[OrderPlaced]): ...     # handles an *event*
```

The asymmetry is not just aesthetic:

- **`Handler` no longer says what it handles.** Every docs page that discusses both kinds
  has to qualify it in prose — the handlers guide literally opens with "This page covers
  *request* handlers" to disambiguate. The name should carry that information itself.
- **The family is about to grow.** Issue #12 (streaming handlers) will add a third
  dispatch kind. `RequestHandler` / `EventHandler` / `StreamHandler` (or whatever ADR
  names it) is a coherent family; `Handler` / `EventHandler` / `StreamHandler` reads as
  though requests are handled by a generic base the others derive from, which is false —
  the three are siblings.
- **Precedent.** MediatR, the design ancestor for this library's pipeline behaviors,
  distinguishes `IRequestHandler` from `INotificationHandler` for exactly this reason.
- **Timing.** Under ZeroVer a rename is a minor bump, and at 0.3.x the user base is at
  its smallest it will ever be. Every release that ships more docs, examples, and user
  code on the old name raises the cost of fixing it later.

`Handler` is one of the surfaces CI flags as a potential breaking change and one of the
surfaces the versioning policy names explicitly — hence this ADR.

## Proposed Solution(s)

### Option A — rename with a one-release deprecated alias (RECOMMENDED)

Rename the class to `RequestHandler` in both `pymediate` and `pymediate.aio`, put
`RequestHandler` in `__all__`, and keep `Handler` importable for one minor release via a
module-level `__getattr__` that emits a `DeprecationWarning`:

```python
# pymediate/__init__.py (same pattern in pymediate/aio/__init__.py)
from .handler import RequestHandler

def __getattr__(name: str) -> Any:
    if name == "Handler":
        warnings.warn(
            "pymediate.Handler was renamed to RequestHandler in 0.4.0; "
            "the Handler alias will be removed in the next minor release.",
            DeprecationWarning,
            stacklevel=2,
        )
        return RequestHandler
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
```

Pros:

- Existing code keeps running through 0.4.x with a clear, actionable warning at import.
- The warning fires exactly once per import site (`from pymediate import Handler`), not
  per dispatch — zero hot-path cost.
- `__getattr__` is the stdlib-sanctioned pattern (PEP 562) used by numpy/pandas for
  precisely this migration shape; no runtime dependency needed (PEP 702's
  `warnings.deprecated` requires Python 3.13 or `typing_extensions`, and the core is
  zero-dependency).

Cons:

- Under type checkers the deprecated name degrades: mypy/pyright resolve module
  `__getattr__` results as `Any`, so `class X(Handler[R])` still type-checks but loses
  inference until the import is updated. This is arguably a feature (a nudge with no
  runtime breakage), but it is silent.
- The alias must actually be removed next minor, or it becomes permanent surface.

### Option B — rename with a permanent typed alias

`Handler = RequestHandler` as a real module attribute, documented as deprecated but never
warned about and never removed.

Pros: nothing breaks, full typing preserved on both names.
Cons: two names for one class forever; docs, editors, and code review must keep
explaining which is canonical; the ambiguity this ADR exists to remove survives.

### Option C — keep `Handler`, name future kinds around it

Accept `Handler` as the request handler's name permanently.

Pros: no migration at all.
Cons: the prose-qualification problem is permanent and compounds with every new handler
kind; the cheapest moment to fix it (now) is spent.

## Decision

Option A.

- `RequestHandler` becomes the canonical name in `pymediate` and `pymediate.aio` (the two
  are structural mirrors and change together).
- `Handler` remains importable in 0.4.x via PEP 562 `__getattr__` with a
  `DeprecationWarning`; it is dropped from `__all__` immediately and removed entirely in
  the next minor release.
- Module paths do not change: the class lives in `pymediate/handler.py` /
  `pymediate/aio/handler.py` as before. Modules group concepts (`event.py` holds both
  `Event` and `EventHandler`); the public contract is `__init__.py`'s `__all__`, not
  module paths.
- Internal names (`HandlerBaseMixin`, registry vocabulary, `_resolve_handler`) keep using
  "handler" as the umbrella term for both kinds — `_internal/` has no compatibility
  surface and the umbrella reading is correct there.
- Error types (`HandlerNotFoundError`, `HandlerAlreadyRegisteredError`,
  `InvalidHandlerSignatureError`) are **not** renamed: they already apply across both
  handler kinds (`InvalidHandlerSignatureError` is raised for event handlers too), so
  "handler" is accurate, and renaming them would multiply the breakage for no clarity
  gain.

## Consequences

### Positive

- The public vocabulary states what each class does: `RequestHandler` handles requests,
  `EventHandler` handles events, and future kinds join a consistent family.
- Docs and docstrings can stop qualifying "handler" in prose.
- Alignment with the MediatR naming users may already know.

### Negative

- Every consumer must eventually rename imports and base classes (mechanical, but real).
- Every internal surface quoting the old name must move in lockstep in one change:
  source docstrings, tests, the typing-snippet corpus and its pinned diagnostics in
  `tests/typing/expectations.py` (checker messages quote the class name), docs site
  (including the `api/handler` page URL), README, home page, benchmark script,
  `CLAUDE.md`, and the examples suite. A stray old-name reference in checker
  expectations fails CI, which is the safety net working.
- The examples in `examples/` demonstrate the released PyPI package; once updated to
  `RequestHandler` they require ≥ 0.4.0 and are validated by the release pipeline
  against the 0.4.0 TestPyPI candidate, not against 0.3.1.

## Migration Path

For users, in 0.4.x:

```python
# before
from pymediate import Handler
class CreateUserHandler(Handler[CreateUser]): ...

# after
from pymediate import RequestHandler
class CreateUserHandler(RequestHandler[CreateUser]): ...
```

Same substitution for `pymediate.aio`. The old name keeps working through 0.4.x with a
`DeprecationWarning` naming the replacement; it disappears in the next minor release.
The rename ships in 0.4.0 (minor bump — a changed name in `__all__`, per the versioning
policy).

## Open Questions

- Should the removal release also be the streaming release (so 0.5.0 both removes the
  alias and introduces the third handler kind)? Tentative lean: yes — one migration
  window, and the family naming lands complete.
