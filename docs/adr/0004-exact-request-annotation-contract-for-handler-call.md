# ADR 0004: Exact request-annotation contract for Handler.__call__

**Status:** Proposed
**Date:** 2026-07-10
**Author:** Claude
**Reviewers:** @sina-al

## Context

When a `Handler[RequestT]` subclass is defined, `__init_subclass__` validates the `__call__`
signature at class-definition time (`_validate_call_signature()` in
`src/pymediate/_internal/handler.py`). The request parameter's annotation is compared against
the request class declared in `Handler[...]` with **exact equality** — a base class, a union,
or any other supertype is rejected:

```python
@dataclass
class CreateUserRequest(Request[UserResponse]):
    username: str

class CreateAdminRequest(CreateUserRequest):
    admin_level: int = 1

class CreateUserHandler(Handler[CreateAdminRequest]):
    # Annotating the base class raises at import time:
    # InvalidHandlerSignatureError: __call__ parameter must be of type
    # myapp.requests.CreateAdminRequest, got myapp.requests.CreateUserRequest
    def __call__(self, request: CreateUserRequest) -> UserResponse: ...
```

This contract exists but is invisible until it bites (issue #9):

- **Static checkers permit the broader annotation.** Widening a parameter type in an override
  is contravariance — perfectly legal to mypy and basedpyright. So a user who annotates a base
  class gets no editor squiggle and no `mypy --strict` error; the first signal is a runtime
  exception at import time.
- **The error message doesn't teach the rule.** "must be of type X, got Y" reads as a plain
  mismatch. When Y is a *base class* of X, the user reasonably believes their annotation is
  compatible (it would be, for an ordinary override) and can't tell what PyMediate actually
  wants or why.
- **The docs never state the contract.** Neither the handlers guide nor the troubleshooting
  page says the annotation must be the exact class.

Issue #9 asks for a decision: document the exact-match contract as-is, or relax the validator
to accept `issubclass`-compatible annotations.

## Proposed Solution(s)

### Option A — Keep the exact-match contract; document and teach it (RECOMMENDED)

No change to validation semantics. Three additions:

1. The mismatch branch of `_validate_call_signature()` says explicitly that the exact class
   is required and names the `Handler[...]` declaration as the source of truth (the error
   already appends the troubleshooting-page link via `docs_path`).
2. The handlers guide and the troubleshooting page document the contract and its rationale.
3. The `Handler` docstrings (sync and `aio` mirrors) state "exactly" rather than "matches".

**Pros:**

- Dispatch stays sound. `mediator.send()` resolves handlers by `type(request)` as an exact
  dict key, and `Request[ResponseT]` maps each concrete request class to its response type.
  Exact annotations keep `Handler[X]` ⇔ `def __call__(self, request: X)` a single,
  checkable source of truth for that mapping.
- The one-handler-per-request policy (`HandlerAlreadyRegisteredError`) keeps its crisp
  meaning: there is never a question of which handler wins for a given request.
- Patch release — no behavior change beyond a better message.

**Cons:**

- Polymorphic handling (one handler serving a request hierarchy) remains unsupported. Users
  who want shared logic across request types must factor it into shared code called by
  per-request handlers, or compose via the mediator.

### Option B — Relax validation to `issubclass` compatibility

Accept an annotation `A` when `issubclass(expected, A)`:

```python
if not (isinstance(request_annotation, type)
        and issubclass(expected_request_type, request_annotation)):
    raise errors.InvalidHandlerSignatureError(...)
```

**Pros:**

- Matches what static type checkers already accept (contravariant parameter widening).
- Reads as more Pythonic/duck-typed at first glance.

**Cons:**

- **Relaxing the annotation alone changes nothing observable.** Dispatch is keyed by the
  exact request type — a handler declared `Handler[CreateAdminRequest]` receives
  `CreateAdminRequest` instances regardless of how its parameter is annotated. The only real
  effect would be *weakening* the drift check between the type parameter and the
  implementation, the very thing the validation exists to catch.
- To make a base-class annotation *mean* something, dispatch itself would have to walk the
  request's MRO: which handler wins when both `Handler[CreateUserRequest]` and
  `Handler[CreateAdminRequest]` are registered? What does `HandlerAlreadyRegisteredError`
  mean once "already registered" includes ancestors? This is a much larger public-behavior
  change than the annotation rule.
- Response-type inference becomes unsound: a subclass request may declare a different
  `Request[ResponseT]` than its base, but a base-annotated handler has one return annotation.
  `mediator.send()`'s typed return currently relies on the exact mapping.
- Interacts badly with #11 (scoped registries), which builds on exact-key registration.

## Decision

**Option A.** Keep the exact-match contract; make the error message teach it and document it
with rationale:

- Exactness is not incidental strictness — it is what makes single-handler dispatch and
  `send()`'s response-type inference sound. The annotation check is a drift detector between
  `Handler[X]` and the implementation, and a drift detector must be exact.
- Option B either changes nothing (annotation-only) or reopens dispatch semantics,
  handler-uniqueness semantics, and response-type soundness all at once — none of which
  issue #9's papercut justifies.
- The actual problem reported is discoverability, and that is fully fixable with a teaching
  error message and documentation. Patch release per the ZeroVer policy.

## Consequences

### Positive

- The confusing failure mode becomes self-explaining: the error states the rule, shows the
  fix, and links to a docs section that gives the rationale.
- The contract is written down where users look (guide, troubleshooting, docstrings), so it
  stops being an undocumented surprise.
- Dispatch, registration, and response inference semantics are untouched — zero risk.

### Negative

- Request-hierarchy polymorphism stays off the table. If a compelling use case emerges, it
  should arrive through #11 (scoped registries) or a future ADR that redesigns dispatch
  deliberately, not through a loosened annotation check.

## Migration Path

No migration needed — validation semantics are unchanged; only the error message text and
documentation change.

## Open Questions

- Should #11 (scoped registries) ever introduce hierarchy-aware lookup, does this contract
  need revisiting? Lean: no — scoped registries change *where* a handler is registered, not
  *which* request types it claims, so exact annotations remain the right invariant there too.
