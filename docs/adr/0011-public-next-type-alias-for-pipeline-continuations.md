# ADR 0011: Public `Next` type alias for pipeline behaviour continuations

**Status:** Proposed
**Date:** 2026-07-12
**Author:** Claude
**Reviewers:** @sina-al

## Context

`PipelineBehavior.__call__`'s `next` parameter — the continuation a behaviour calls to run
the rest of the pipeline — carries a verbose callable annotation that the async-first
inversion (ADR 0008) pushed to the front of the documentation. `next` is now the noisiest
type on the library's most-documented method:

```python
# async (top-level pymediate)
async def __call__(self, request: RequestT, next: Callable[[], Awaitable[Any]]) -> Any: ...

# sync (pymediate.sync)
def __call__(self, request: RequestT, next: Callable[[], Any]) -> Any: ...
```

That spelling is repeated verbatim across the abstract signatures (both mirrors), the source
docstrings, `docs/content/docs/api/pipeline.mdx`, `docs/content/docs/guide/pipeline-behaviors.mdx`,
and every typed pipeline snippet. A behaviour author who wants a typed continuation writes
`Callable[[], Awaitable[UserResponse]]` — three nested constructors and two imports
(`Awaitable`, `Callable` from `collections.abc`) for what is conceptually "the thing that
returns a `UserResponse`".

Issue #39's Phase 3 flagged `next: Callable[[], Any]` as public-API `Any`-leakage worth
auditing. The `Any` in the *abstract* signature is deliberate (a base class can't know the
response type — see the `should_apply`/selective-behaviour design in ADR 0002), but nothing
gives authors a clean, generic way to name the response at their own call site.

There is one design tension to clear. ADR 0002's open question #3 explicitly considered — and
leaned against — a typing helper:

```python
from pymediate.typing import ResponseOf
def __call__(self, request: MyRequest, next) -> ResponseOf[MyRequest]: ...  # rejected
```

That was rejected because `ResponseOf[MyRequest]` tried to *derive* a response type from the
request type, which no static checker can do through the erased pipeline. This proposal is a
different animal: a plain spelling alias for the callable, generic over a response type the
author supplies explicitly. It changes no semantics and asks nothing of the checker's
inference — it only renames a type users already write by hand.

## Proposed Solution(s)

### Option A: A public, generic `Next[ResponseT]` alias, one per mirror (RECOMMENDED)

Define a PEP 695 `type` alias in each pipeline module and export it top-level:

```python
# src/pymediate/pipeline.py (async)
type Next[ResponseT] = Callable[[], Awaitable[ResponseT]]

# src/pymediate/sync/pipeline.py (sync)
type Next[ResponseT] = Callable[[], ResponseT]
```

A behaviour author then writes:

```python
from pymediate import Next, PipelineBehavior, Request

class Timing(PipelineBehavior[GetUser]):
    async def __call__(self, request: GetUser, next: Next[UserResponse]) -> UserResponse:
        return await next()
```

The abstract `__call__` signatures become `next: Next[Any]` — same meaning as before, spelled
through the alias so the base class documents the alias it expects subclasses to use.

**Pros:**

- Collapses the noisiest type on the most-documented method to `Next[ResponseT]`, and drops the
  `collections.abc` import from authoring code entirely.
- Generic-over-response preserves the concrete-response typing the valid snippets already use
  (`Next[UserResponse]` binds the call site, exactly as `Callable[[], Awaitable[UserResponse]]`
  did) — a flat `Any` alias would force users back to spelling out the callable.
- Async (`Awaitable[T]`) and sync (`T`) genuinely differ, so `Next` naturally slots into the
  existing `INTENTIONAL_VARIANTS` parity model (ADR 0008) beside the handler/mediator/behaviour
  classes — one more name that legitimately differs between the mirrors.
- Pure spelling change: no runtime behaviour, no checker-inference demands, so it sidesteps the
  reason ADR 0002 rejected `ResponseOf`.

**Cons:**

- A new public name in `__all__` is a (backward-compatible) surface expansion — one more thing
  to keep mirrored and documented.
- `Next` is the same identifier as the built-in `typing` conventions some readers associate with
  other frameworks; mitigated by it being generic and pipeline-scoped in the docs.

### Option B: Flat, non-generic alias (`type Next = Callable[[], Awaitable[Any]]`)

**Pros:** even shorter; no type parameter to explain.
**Cons:** throws away response typing — a behaviour that wants `Next[UserResponse]` would have to
abandon the alias and hand-write the callable again, which is the exact verbosity this exists to
remove. Rejected.

### Option C: A `pymediate.typing` submodule housing the alias

**Pros:** keeps the top-level namespace lean; a natural home if more typing helpers arrive later.
**Cons:** one symbol doesn't justify a new public module and a second import path; behaviours
already import `PipelineBehavior` from the top level and `Next` belongs beside it. Rejected —
revisit only if a family of typing aliases materialises.

## Decision

Option A, matching issue #71's locked decisions:

- **Generic** `type Next[ResponseT]` — async resolves to `Callable[[], Awaitable[ResponseT]]`,
  sync to `Callable[[], ResponseT]`.
- **PEP 695 `type` statement**, not `typing.TypeAlias` or a plain assignment. There is no
  existing alias precedent in `src/pymediate/`; this establishes the convention and matches the
  uniformly-PEP-695 style (`class X[T: Bound]`, `def m[T](...)`).
- **Top-level public export** in both `pymediate.__all__` and `pymediate.sync.__all__`, in the
  `# Pipeline` group beside `PipelineBehavior`. Not a new submodule (Option C rejected).
- **Parity:** `Next` joins `INTENTIONAL_VARIANTS` in `tests/test_parity.py` — the two sides are
  distinct objects by design. It is *not* added to `test_variants_split_async_and_sync`, which
  introspects `__call__` coroutine-ness on classes; an alias has no `__call__`.
- **Adopt everywhere now:** the abstract signatures (both mirrors), source docstrings, the API
  reference and pipeline guide, and the typed pipeline snippets all switch to `Next`. Delivering
  the documentation cleanup is the point of the change.
- **Scope guard:** `src/pymediate/_internal/pipeline.py` is untouched. Its
  `Callable[[Any], Awaitable[Any]]` types describe `next_step`, the chain-composition callable
  that *takes the request* — a different object from the zero-arg `next` handed to behaviours.
  The alias is the public behaviour boundary only.
- **Versioning:** a **minor** bump per ZeroVer — a new name in `__all__` is a
  backward-compatible feature.

Relationship to prior records: this does **not** overturn ADR 0002. That ADR rejected a helper
that derived response types from request types; `Next[ResponseT]` derives nothing and takes the
response type as an explicit parameter. The abstract signature's `Next[Any]` keeps ADR 0002's
"the base class is honest about not knowing the response" stance intact.

## Consequences

### Positive

- Behaviour signatures read as intent: `next: Next[UserResponse]` instead of
  `next: Callable[[], Awaitable[UserResponse]]`, with fewer imports.
- The most-copied type in the docs is now a named, documented alias with IDE hover text, rather
  than a bare callable users pattern-match by eye.
- The generic parameter keeps the typed-continuation experience the snippet corpus already
  verifies under mypy `--strict` and basedpyright (both modes).

### Negative

- Public surface grows by one name on each side; the mirror and its documentation must stay in
  sync (now enforced by the parity test).
- Existing user code written against `Callable[[], Awaitable[...]]` keeps working but reads
  differently from the docs until authors migrate — a cosmetic, opt-in drift, not a break.

## Migration Path

No migration needed. `Next` is additive: `Callable[[], Awaitable[ResponseT]]` (async) and
`Callable[[], ResponseT]` (sync) remain valid annotations for `next` — `Next[ResponseT]` is
definitionally the same type, so existing behaviours type-check unchanged. Authors may adopt the
alias at their own pace.

## Open Questions

- Should the docs recommend `Next` (and `@override`) as the default authoring style in the
  examples that currently use unannotated `def __call__(self, request, next):`? Tentative lean:
  **no** — those untyped examples deliberately show the minimal spelling, and issue #71 scoped
  them out. Revisit if users report the two styles are confusing side by side.
- If more typing helpers ever join `Next`, does a `pymediate.typing` module (Option C) become
  worthwhile? Tentative lean: **defer** until there's a second symbol to house.
