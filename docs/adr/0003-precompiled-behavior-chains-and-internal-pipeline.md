# ADR 0003: Precompiled behavior chains and an internal pipeline

**Status:** Proposed
**Date:** 2026-07-09
**Author:** Claude
**Reviewers:** @sina-al

## Context

Profiling the dispatch path (2026-07-09, CPython 3.13, Intel macOS; medians of tight-loop
`timeit` runs against the local source) showed that pipeline behaviors cost far more than
the two extra stack frames they inherently require, and that `send()` degrades linearly
with the *total* number of registered services:

| Component | Cost | Cause |
| --- | ---: | --- |
| Direct handler call (baseline) | 330 ns | — |
| `registry.get_handler_class` | 288 ns | `RLock` acquired on every send for a read-only dict lookup |
| `provider.get_all(PipelineBehavior)` | 853 ns | isinstance-scan of **every** registered service instance, per send |
| `PipelineBehavior.should_apply` | 996 ns | `__get_request_type__` re-walks `__orig_bases__` with `get_origin`/`get_args` on every call |
| `Pipeline.__call__`, 1 behavior | 3,580 ns | rebuilds the whole closure chain per call, defines a factory function per behavior per call, and executes `from typing import cast` inside the hot path |
| **`mediator.send()`, 1 behavior, end to end** | **8,047 ns** | 24x the direct call |

The scaling result is the sharpest problem. `send()` with **zero** behaviors registered:

| Registered services | `send()` per call |
| --- | ---: |
| 2 | 1.9 µs |
| 12 | 4.5 µs |
| 52 | 14.5 µs |
| 202 | 55.8 µs |

Every handler an application registers slows down every dispatch, because
`_resolve_behaviors` calls `ServiceProvider.get_all(PipelineBehavior)`, which scans the
full registration list. A statically composed chain (closures built once, called
repeatedly) measures **718 ns** for direct-call-plus-one-behavior — so roughly 95% of the
current per-behavior cost is removable, not inherent.

### The API problem is the same problem

`Pipeline` as a public class has independent design flaws, and they share a root cause
with the performance flaws — the class is designed as a per-request throwaway that the
mediator constructs inside `send()`:

```python
class Pipeline[RequestT, ResponseT]:
    def __init__(self, behaviors: Sequence[Any], handler: Handler[RequestT]) -> None: ...
    def __call__(self, request: RequestT) -> ResponseT: ...
```

- **The typing is decorative.** `behaviors: Sequence[Any]` in a library whose pitch is
  type safety, and `ResponseT` can never be inferred at the constructor because
  `Handler.__call__` returns `Any`. Both type parameters exist only in the signature.
- **Not closed under composition.** A `Pipeline` is neither a `Handler` nor a
  `PipelineBehavior`, so pipelines can't nest, a behavior chain can't be reused across
  handlers, and "composing two pipelines" means manually merging their behavior lists.
- **Coupling to `Handler`.** Bundling the chain with its terminal handler means a
  pipeline isn't a reusable value — it's a one-shot binding that only the mediator
  actually needs.

Notably, `Pipeline` is **not** in the top-level `__all__` — only `PipelineBehavior` is.
Under the versioning policy (breaking = `__init__.py`'s `__all__`, `Handler`, or the
`ServiceProvider` protocol), reshaping or internalizing `Pipeline` is not a breaking
change, though it is documented in `docs/api/` and deserves a deprecation note.

### What must not change

Two documented contracts constrain any redesign:

1. `should_apply` is overridable with **dynamic** logic (the docstring's
   `BusinessHoursBehavior` example gates on time of day) — behavior *selection* cannot be
   blanket-cached per request type.
2. Service providers control instance lifetimes (`dependency-injector`'s `Factory`
   resolves a fresh instance per request) — behavior *instances* cannot be cached by the
   mediator.

## Proposed Solution(s)

### Option A: Optimize in place, keep `Pipeline` public as-is

Fix the mechanical waste without touching any signature: extract the behavior's request
type once at class creation (`__init_subclass__`) instead of per `should_apply` call;
compose the closure chain once in `Pipeline.__init__` instead of per `__call__`; hoist
the `cast` import; drop the read-locks in the registry (CPython dict reads are atomic;
writes keep the lock); memoize `get_all` results per requested base type inside
`_Provider` (it is an immutable snapshot, so the cache can never go stale).

**Pros:**

- Ships immediately as a patch release; no docs or API churn.
- Removes the O(N) scan and ~90% of per-behavior overhead.

**Cons:**

- `Pipeline`'s design flaws (decorative generics, `Sequence[Any]`, no composability)
  remain public and documented.
- The mediator still builds a `Pipeline` object per send — small but avoidable.

### Option B: Option A + internalize the pipeline (RECOMMENDED)

Everything in Option A, plus: move the chain-composition machinery to `_internal/`,
remove the `Pipeline` class from the public API and its `docs/api/` page, and leave
`PipelineBehavior` as the *only* public pipeline concept. The mediator composes the chain
directly — per send it resolves applicable behavior instances (honoring `should_apply`
and provider lifetimes), links them with one small closure per behavior, and invokes the
handler. Manual composition without a mediator remains trivially possible in user code
(`behavior(request, lambda: handler(request))`), which the docs can show in one line
where they currently point at `Pipeline`.

**Pros:**

- The public surface tells the truth: users define behaviors, the mediator runs them.
  There is no half-typed, non-composable class to explain or maintain compatibility for.
- Internal machinery can then change shape freely (e.g. flattening the chain into a loop)
  under `_internal/`'s no-back-compat rule.
- Deletes ~130 lines of public docstrings that document the awkwardness.

**Cons:**

- A documented class disappears; anyone constructing `Pipeline` manually (undocumented
  outside the API reference, but public) must inline the composition themselves.
- Requires a docs sweep: `docs/api/pipeline.md`, guide pages, and docstring `See Also`
  references to `Pipeline`.

### Option C: Public behavior composition (`compose()`)

Expose a `compose(*behaviors) -> PipelineBehavior` utility: a chain of behaviors *is a
behavior* (closed under composition, handler-free), fixing the composability complaint
directly rather than by removal.

**Pros:**

- Composition becomes a first-class, well-typed operation; composed chains register and
  select like any behavior.

**Cons:**

- New public API solving a problem no user has reported; `should_apply` semantics for a
  composed chain (outer gate vs. per-member gates) need design of their own.
- Can be layered on top of Option B later without conflict.

## Decision

Option B, in two independently shippable stages:

- **Stage 1 (Option A, patch):** the semantics-preserving optimizations. No public API
  impact; every existing test must pass unchanged. This lands regardless of this ADR's
  review outcome, since it changes no documented behavior.
- **Stage 2 (pending review of this ADR):** internalize `Pipeline`, update docs, and keep
  `PipelineBehavior` as the sole public pipeline concept.
- Option C is explicitly deferred: revisit if a concrete need for reusable, registrable
  behavior chains appears (tracked informally; no issue yet).

Rationale:

- The measured waste is real but fully mechanical — nothing about the mediator pattern
  requires it. Fixing it in place (Stage 1) is low-risk and immediately improves the
  published benchmark story.
- The `Pipeline` class's problems are structural, not cosmetic; polishing its internals
  while leaving the shape public would preserve an API that misleads (decorative
  generics) and can't compose. Internalizing is the honest fix and, per the versioning
  policy, not formally breaking.

## Consequences

### Positive

- `send()` overhead becomes independent of how many unrelated services are registered.
- Per-behavior marginal cost drops from ~4.7 µs to the order of one closure allocation
  and one extra frame (~0.3–0.5 µs).
- The comparison page's benchmark rows improve without changing methodology.
- Public API shrinks to the parts that are actually type-safe.

### Negative

- `pymediate.pipeline.Pipeline` (and `pymediate.aio.pipeline.Pipeline`) disappear from
  the API docs; external code constructing them directly (likely rare — never shown in
  guides or README) must inline the one-line composition.
- Registry reads become lock-free: relies on CPython's atomic dict operations, which is
  a documented-in-code assumption rather than an enforced one (true today for all
  supported CPython versions; free-threaded builds keep per-dict internal consistency).

## Migration Path

Stage 1: none — no public API impact.

Stage 2: not formally breaking (surfaces per the versioning policy are untouched), but
ship it in a **minor** release with a note: "`Pipeline` was removed from the public API;
to run behaviors without a mediator, call them directly:
`behavior(request, lambda: handler(request))`."

## Open Questions

- Should Stage 2 also rename `PipelineBehavior.__get_request_type__` (public-ish dunder
  on a public class) to a plain `_internal` helper while the surface is already moving?
  Lean: yes, it was never meant to be called by users.
- Does the aio mirror need an async `compose()` story if Option C is ever revisited?
  Lean: decide when C is revisited; the sync/async mirror rule makes it mechanical.
