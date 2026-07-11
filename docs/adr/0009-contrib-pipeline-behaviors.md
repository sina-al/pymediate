# ADR 0009: A `contrib` module of in-box, zero-dependency pipeline behaviors

**Status:** Proposed
**Date:** 2026-07-11
**Author:** Claude
**Reviewers:** @sina-al

## Context

Issue #13 proposes a `contrib` module of batteries-included `PipelineBehavior`s —
logging, timing, retry — built from the standard library only, so the zero-runtime-dependency
guarantee holds. Several surveyed alternatives bundle logging middleware; the issue's thesis is
that PyMediate's *selective* behaviors (`PipelineBehavior.should_apply`, ADR 0002) make bundled
behaviors more useful than theirs, "since users can scope a bundled behavior to a subset of
requests without subclass gymnastics."

Today a user hand-writes every behavior. The docs guide
(`docs/content/docs/guide/pipeline-behaviors.mdx`) already ships hand-written **Logging**,
**Retry with backoff**, and **Transaction** *recipes* — so the raw capability exists; what's
missing is a supported, tested, importable version.

Two things must be settled before writing any behavior code, and both turned out to be more
subtle than the issue anticipated:

1. **The issue's namespace is stale.** It says `pymediate.aio.contrib`. Since ADR 0008
   (async-first package inversion) the async API is the top-level `pymediate` and the sync
   mirror is `pymediate.sync`; `pymediate.aio` no longer exists. An in-package `pymediate.contrib`
   was the first correction — but the Decision below goes further and puts contrib in a **separate
   distribution** imported as top-level `pymediate_contrib` (see "Packaging").

2. **"Scope a bundled behavior without subclass gymnastics" collides with how selection
   actually works.** `should_apply` is a **classmethod** resolved per behavior *class*, not per
   *instance* — the dispatcher calls `type(behavior).should_apply(request)`
   (`_internal/mediator.py:119`). A bundled behavior registered as an instance therefore can't
   carry per-instance scope through the existing mechanism. The only in-framework way to scope a
   behavior is its type parameter (`PipelineBehavior[SomeRequest]`), resolved once in
   `__init_subclass__`. That pushes any batteries-included behavior toward being **generic**
   (`RetryBehavior[RequestT]`) so a caller can scope it with a one-line subclass
   (`class OrderRetry(RetryBehavior[CreateOrder]): ...`). **Prototyping that against the current
   base class revealed two defects** (see Investigation).

### Minimal example of the intended usage

```python
from pymediate import Mediator, Services
from pymediate_contrib import LoggingBehavior, RetryBehavior  # pip install pymediate-contrib

services = (
    Services()
    .add(CreateOrderHandler())
    .add(LoggingBehavior())            # universal: logs every request
    .add(RetryBehavior(attempts=3))    # universal: retries every request
)
mediator = Mediator(services.provider())
```

## Investigation

The design hinges on whether a *generic* contrib behavior can be (a) registered directly for
universal use and (b) scoped by a one-line subclass. Both were prototyped against the real base
class (`src/pymediate/pipeline.py`), and both currently fail.

The base resolves a behavior's request type in `__init_subclass__`
(`pipeline.py:127-141`) by scanning `__orig_bases__` for a base whose origin **is exactly
`PipelineBehavior`**, taking its first type argument, and storing the `get_origin`-resolved form
as `__match_type__`. `should_apply` then does `isinstance(request, __match_type__)`.

**Defect 1 — direct generic registration crashes.** Given

```python
class RetryBehavior[RequestT: Request[Any]](PipelineBehavior[RequestT]):
    ...
```

the extracted type argument is the *TypeVar* `RequestT`, so `__match_type__` is `RequestT`, and

```python
RetryBehavior.should_apply(CreateOrder())
# TypeError: isinstance() arg 2 must be a type, a tuple of types, or a union
```

**Defect 2 — subclass-to-scope is silently ignored.** Given `class OrderRetry(RetryBehavior[CreateOrder]): pass`,
`OrderRetry.__orig_bases__` is `(RetryBehavior[CreateOrder],)` whose origin is **`RetryBehavior`,
not `PipelineBehavior`**. The scan finds no matching base, falls back to `Request`, and:

```python
OrderRetry.__request_type__          # -> pymediate.request.Request   (expected: CreateOrder)
OrderRetry.should_apply(OtherReq())  # -> True                        (expected: False)
```

The `CreateOrder` narrowing is lost with no error — `OrderRetry` applies to *everything*. This is
the more dangerous of the two.

Both defects share one root cause: the current resolver assumes exactly one generic layer
(`class MyBehavior(PipelineBehavior[SomeRequest])`) and does not handle an **intermediate
generic base** or an **unsubscripted TypeVar**. That single-layer assumption was correct for
every behavior written to date, because none introduced a reusable generic middle class — which
is exactly what a `contrib` behavior is.

## Proposed Solution(s)

### Option A — Universal-only contrib behaviors (no generics, no base change)

Ship each behavior as a concrete, non-generic `PipelineBehavior[Request]`, configured entirely
through its constructor:

```python
class LoggingBehavior(PipelineBehavior[Request]):
    def __init__(self, logger: logging.Logger | None = None, level: int = logging.INFO) -> None:
        self._logger = logger or logging.getLogger("pymediate")
        self._level = level
    async def __call__(self, request: Request, next: Callable[[], Awaitable[Any]]) -> Any:
        ...
```

Scoping a bundled behavior to a subset is **not supported**; a user who needs it writes their own
`PipelineBehavior` subclass (or overrides `should_apply`), as they do today.

**Pros**
- Zero change to the flagged `PipelineBehavior` surface; smallest, safest, ships now.
- Trivially typed and understood; matches the existing single-layer resolver.

**Cons**
- Abandons the issue's headline value ("scope a bundled behavior to a subset"). The contrib
  behaviors become pure convenience, not a `should_apply` showcase.
- Users who want a scoped retry get no help from the batteries — they reimplement it.

### Option B — Generic contrib behaviors + harden the base resolver (RECOMMENDED)

Make each behavior generic and fix `__init_subclass__` to support intermediate generic layers and
unsubscripted TypeVars:

```python
class RetryBehavior[RequestT: Request[Any]](PipelineBehavior[RequestT]):
    def __init__(self, attempts: int = 3, ...) -> None: ...
    async def __call__(self, request: RequestT, next: Callable[[], Awaitable[Any]]) -> Any: ...
```

The base resolver changes from "find a direct `PipelineBehavior[...]` base" to "walk the generic
ancestry (`__orig_bases__` transitively / the `__mro__`) for the argument that fills
`PipelineBehavior`'s type parameter, and if it resolves to a `TypeVar`, treat it as the TypeVar's
bound (→ `Request`, i.e. universal)." Concretely:

- `RetryBehavior(attempts=3)` → universal (TypeVar resolved to `Request`), applies to all
  requests. Fixes Defect 1.
- `class OrderRetry(RetryBehavior[CreateOrder]): pass` → `__match_type__ == CreateOrder`,
  `should_apply` narrows correctly. Fixes Defect 2.

This is a **backward-compatible widening**: every behavior that resolved before still resolves to
the same type (single-layer, concrete arg), and two shapes that previously misbehaved (crash /
silent-universal) now behave correctly. Arguably worth doing on its own merits, independent of
contrib.

**Pros**
- Delivers the issue's promise using the *existing* `should_apply` mechanism (consistent with
  ADR 0002), not a parallel one.
- Fixes two real latent defects in the generics resolver.
- Scoping is one fully-typed line; `request: RequestT` narrows statically in `__call__`.

**Cons**
- Touches `PipelineBehavior.__init_subclass__` — a CI-flagged breaking-change surface — so it
  needs careful tests and mypy-snippet coverage (both `valid/` scoping and an `errors/` misuse
  case), and a note in this ADR's lineage alongside 0002/0003.
- "One-line subclass" is still technically a subclass — see Option C for the literal reading of
  "without subclass gymnastics."

### Option C — Per-instance scoping hook in the dispatcher

Honor an *instance-level* predicate so scoping needs no subclass at all:

```python
services.add(RetryBehavior(attempts=3, applies_to=CreateOrder))
services.add(RetryBehavior(attempts=1, applies_to=(ReadModel,)))
```

This requires the dispatcher to consult the instance, not just the class — e.g.
`_resolve_behaviors` calls an instance method that defaults to delegating to the classmethod. That
is a change to the ADR-0003 dispatch contract (which deliberately kept selection classmethod-based
and cache-friendly), and it makes two instances of the same class select differently — new
conceptual surface.

**Pros**
- Literally matches "scope a bundled behavior without subclass gymnastics."
- Most ergonomic for the common case (scope one bundled behavior to one request type).

**Cons**
- Expands the core selection contract for *every* behavior, not just contrib — the largest blast
  radius of the three, on the most performance-sensitive path (ADR 0003).
- Two registration idioms for scoping (type param *and* `applies_to`) dilute the "one obvious
  way" story.
- Instance-varying `should_apply` interacts with the memoized `get_all` and the "selection can't
  be cached per request type" invariant from ADR 0003 — needs re-examination.

## Decision

**Scoping: Option B** (confirmed with the maintainer). It reuses the documented
`should_apply`/type-parameter mechanism rather than growing a second scoping idiom, fixes two
genuine latent defects, and keeps the change inside the class-definition-time model the library
already commits to. The base-resolver hardening is a backward-compatible bugfix that stands on its
own, and has **already landed** ahead of the behaviors as commit
`fix: resolve PipelineBehavior request type through generic bases` — with regression tests in
`tests/test_pipeline*.py` and a `valid/` typing snippet
(`tests/typing/snippets/valid/pipeline_generic_behavior_scoped.py`).

**Packaging: a separate `pymediate-contrib` distribution** (confirmed with the maintainer),
imported as its own top-level package `pymediate_contrib` — **not** `pymediate.contrib`, and **not
shipped in the core `pymediate` wheel**. Rationale below. Because a second distribution needs its
own release lane, that infrastructure is designed and built under a **prerequisite issue first**
(issue #63); the behaviors block on it (see Consequences and Open Questions).

The three behaviors, all zero-dependency and mirrored across `pymediate_contrib` (async) /
`pymediate_contrib.sync` (sync), each importing `PipelineBehavior`/`Request` from the core
`pymediate` / `pymediate.sync`:

- **`LoggingBehavior`** — `logging` stdlib. Logs request type on entry; response type / exception
  and elapsed time on exit. `__init__(logger=None, level=logging.INFO)`.
- **`TimingBehavior`** — `time.perf_counter()` around `next()`; reports elapsed seconds to a
  required `on_complete: Callable[[Request[Any], float], None]` callback (no hidden logging
  config, fully predictable, testable).
- **`RetryBehavior`** — plain loop; `time.sleep` (sync) / `asyncio.sleep` (async). Tiny, fixed
  API: `__init__(attempts=3, retry_on=(Exception,), backoff=0.0, backoff_factor=1.0)`. Runs
  `next()`; on an exception in `retry_on` with attempts remaining, sleeps
  `backoff * backoff_factor**(n-1)` and retries; on exhaustion re-raises the last exception.

Deliberately excluded to keep the API tiny: jitter, `max_backoff`, per-exception policies, circuit
breaking, caching-as-retry. These are a documented "roll your own / future ADR" boundary, not v1.

### Packaging, parity, and versioning

A separate `pymediate-contrib` distribution, imported as top-level `pymediate_contrib`:

- **Why a distinct top-level name, not `pymediate.contrib`.** `pymediate` is a *regular* package
  (its `__init__.py` holds the whole API), so it is not a PEP 420 namespace. Contributing a
  `pymediate.contrib` submodule *from a second distribution* would mean two wheels writing into the
  same `pymediate/` directory (the "add-on to a regular package" pattern) — workable but fragile
  across editable installs, type-checker discovery, and `py.typed`. A distinct top-level
  `pymediate_contrib` package sidesteps all of it: standard packaging, its own `py.typed`, its own
  version, no shared-directory hack.
- **Why a separate distribution at all.** The maintainer's constraint is that contrib does not ship
  in the core wheel. An extra (`pymediate[contrib]`) can't achieve this — extras gate
  *dependencies*, not first-party modules — so out-of-wheel necessarily means a second
  distribution. Honest caveat: these three behaviors are zero-dependency, so the split buys
  API-surface purity and an independent release cadence, **not** dependency isolation. It also sets
  up a home for future *dep-carrying* behaviors (e.g. `pymediate-contrib[redis]`) without ever
  touching the core.
- **Parity.** The core `tests/test_parity.py` is unaffected (contrib is not in `pymediate`).
  The contrib project carries its own parity test across `pymediate_contrib` /
  `pymediate_contrib.sync`, mirroring `test_variants_split_async_and_sync`.
- **Versioning.** `pymediate-contrib` versions independently of core through its own release lane;
  its first release is a normal `0.1.0`-style cut, not a bump of `pymediate`.

### Docs reconciliation

The guide's existing hand-written Logging / Retry recipes stay as "here's the mechanism / when to
roll your own," and gain a cross-link to a new **`pymediate_contrib`** section (batteries-included,
`pip install pymediate-contrib`) plus a hand-written `docs/content/docs/api/contrib.mdx`. A new
`examples/` project (via the `example` skill) showcases registering a contrib behavior and scoping
one by subclass.

## Consequences

### Positive
- Supported, tested, importable logging/timing/retry with zero added runtime dependencies, in a
  distribution that keeps the core `pymediate` wheel and its public API surface untouched.
- Two latent generics-resolver defects fixed in core; `class Foo[T](PipelineBehavior[T])` becomes a
  valid, well-defined shape (landed independently).
- The separate-distribution pattern gives future batteries (validation, caching, tracing, ...) a
  home — including *dep-carrying* ones — without ever growing the core.

### Negative
- A second distribution means a second PyPI project, a second Trusted Publisher registration, and a
  `pymediate-contrib` release lane mirroring `release.yml` — real new infrastructure, tracked as a
  **prerequisite issue** that blocks the behaviors. For three zero-dependency behaviors this is a
  deliberate cost paid for surface purity and cadence independence, not dependency isolation.
- The retry behavior re-invokes `next()`, which re-runs the handler **and every behavior inner to
  retry in the chain** — a non-idempotent-handler / double-side-effect footgun. Requires a loud
  `Warning:` in the docstring and explicit ordering guidance in the guide (register retry so only
  idempotent work sits beneath it).

## Migration Path

No migration needed. The core change (the resolver fix) is a backward-compatible bugfix with no
name or signature changes; the behaviors are a wholly separate, additive distribution.

## Resolved decisions (maintainer, 2026-07-11)

- **Scoping → Option B** (generic behavior scoped by a one-line subclass), over Option C's
  per-instance `applies_to`. Keeps one scoping idiom and the cache-friendly classmethod selection
  from ADR 0003; C can be revisited as its own ADR if per-instance scoping is ever demanded.
- **Resolver fix lands first**, independently of the behaviors — done.
- **Packaging → separate `pymediate-contrib` distribution, `pymediate_contrib` top-level import**,
  over an in-wheel submodule or a distinct-name-avoiding namespace add-on.
- **Release infra is a prerequisite issue**, built before the behaviors.

## Open Questions

- **`TimingBehavior` output shape** — required callback (proposed, predictable) vs. defaulting to
  `logging` like `LoggingBehavior`. **Lean: required callback**, so timing has exactly one obvious
  effect and no hidden logger configuration.
- **`RetryBehavior` default `retry_on`** — `(Exception,)` (retry everything) vs. forcing the
  caller to name exceptions. **Lean: `(Exception,)`** for zero-config ergonomics, with the footgun
  called out loudly.
