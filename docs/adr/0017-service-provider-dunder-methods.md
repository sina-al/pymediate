# ADR 0017: Replace `ServiceProvider.get()`/`has()` with `__getitem__`/`__contains__`

**Status:** Proposed
**Date:** 2026-07-22
**Author:** Claude
**Reviewers:** @sina-al

## Context

ADR 0016 (2026-07-20) shrank `ServiceProvider` to exactly the two operations the mediator
uses: `get(service_type)` (exact-type resolution, raising `ServiceNotFoundError` on a miss)
and `has(service_type)` (exact-type membership test). Both are hand-rolled equivalents of
Python's built-in mapping vocabulary — `ServiceProvider` already behaves like a read-only
`Mapping[type, object]` keyed by type:

```python
provider.get(Cache)     # resolve
provider.has(Cache)     # test
```

The idiomatic spelling for "resolve by key" and "test for a key" is indexing and `in`:

```python
provider[Cache]
Cache in provider
```

CLAUDE.md's simplify section calls this out directly: "When an option is designed for the
job (a stdlib/library primitive that does what a hand-rolled helper does), use it, even if
adopting it changes behavior at the edges." `__getitem__`/`__contains__` are exactly that
primitive. The open question was whether the switch could preserve `get()`'s type-safety
guarantee — that `provider.get(Cache)` is inferred as `Cache`, not `Any` or `object`, via a
generic method (`def get(self, service_type: type[ServiceT]) -> ServiceT`) — since a dunder
method is still just a method under the hood, but the guarantee needed verifying before
committing to the change, not assuming it.

## Proposed Solution(s)

### Option A — Replace `get`/`has` with `__getitem__`/`__contains__` (RECOMMENDED)

```python
class ServiceProvider(Protocol):
    def __getitem__(self, service_type: type[ServiceT]) -> ServiceT: ...
    def __contains__(self, service_type: type) -> bool: ...
```

Verified before implementation: a scratch `Protocol` with this shape, checked under both
`mypy --strict` and `basedpyright`, shows `provider[Foo]` inferred as `Foo` (not `Any`) by
both checkers, and `wrong: int = provider[Foo]` is flagged as an error by both — the same
exact-type-preserving inference `get()` has today, carried over losslessly to the dunder
form.

**Pros:**
- One way to resolve a service, using vocabulary every Python programmer already knows.
- No loss of type safety — confirmed empirically, not assumed.
- Fewer protocol methods for a custom `ServiceProvider` implementation to define is not
  the win here (the count is unchanged, two methods either way) — the win is that the two
  methods are the ones Python already gives a meaning to.

**Cons:**
- Breaking change: every internal call site, test, and hand-written docs page that spells
  resolution as `.get(...)`/`.has(...)` needs updating in the same change.
- `__getitem__` raising a domain-specific `ServiceNotFoundError` rather than `KeyError` is a
  half-step away from full `Mapping` idiom (a `try: provider[Foo] except KeyError` reflex
  won't catch it) — accepted as a deliberate choice, not an oversight (see Decision).

### Option B — Add dunders alongside `get`/`has` (rejected)

Keep `get()`/`has()` untouched and add `__getitem__`/`__contains__` as new protocol members
both providers also implement.

**Pros:** No breaking change; smaller diff.

**Cons:** The protocol permanently carries two spellings for the same lookup — exactly the
"parallel APIs for one operation" CLAUDE.md's simplify section says to avoid. Every future
custom `ServiceProvider` implementation and every doc example has two equally-valid ways to
write the same thing, forever.

## Decision

**Option A**, full replacement. Locked with the maintainer (issue #136 Decisions table,
2026-07-22):

- `get()`/`has()` are removed entirely from `ServiceProvider` and both built-in
  implementations (`_Provider` in `src/pymediate/service.py`,
  `DependencyInjectorServiceProvider` in `src/pymediate/providers/dependency_injector.py`) —
  not kept alongside the new dunders. No deprecation shim: a clean break in one release,
  consistent with this package's ZeroVer stance that the cost of breaking is low here.
- `provider[Type]` raises `ServiceNotFoundError`, unchanged — same class, same message, same
  `service_type`/`available_types` attributes `get()` raises today.
  `ServiceNotFoundError`'s class hierarchy is untouched (stays `Exception`-based; it does
  **not** also inherit `KeyError`). The richer, PyMediate-specific error (naming what *is*
  registered) is judged more useful than matching the `Mapping` protocol's exact exception
  type, and changing a public exception's base class is a separate, larger decision than
  this ADR's scope.
- `__len__` and other non-protocol conveniences on the built-in providers are unaffected —
  this ADR only touches the two protocol operations ADR 0016 left in place.

## Consequences

### Positive

- `ServiceProvider` now reads as what it structurally is — a read-only, type-keyed mapping —
  using the vocabulary Python already has for that.
- A custom `ServiceProvider` implementation (e.g. the planned `120-custom-provider` example,
  issue #90) models itself on `__getitem__`/`__contains__`, which most Python developers
  already know how to implement correctly, rather than two arbitrarily-named methods.
- No type-safety regression: verified with both project-mandated checkers before
  implementation.

### Negative

- **Breaking:** every caller of `provider.get(Type)`/`provider.has(Type)` — internal
  (`src/pymediate/_internal/mediator.py`), test, and documentation — must switch to
  `provider[Type]`/`Type in provider` in the same change. ZeroVer minor release.
- `provider[Type]` raising `ServiceNotFoundError` rather than `KeyError` means code written
  against the `Mapping` idiom's usual exception type won't catch a miss without knowing
  PyMediate's specific exception — a readability win (indexing syntax) traded against a
  smaller idiom mismatch (exception type) than doing both would have cost.
- `examples/` are not updated by this ADR's implementation — they pin against the *released*
  package and are migrated as a post-release follow-up via the `example` skill, per
  CLAUDE.md's `examples/` contract.

## Migration Path

Breaking change, shipped in a **minor** release (ZeroVer):

- Replace `provider.get(Type)` with `provider[Type]`.
- Replace `provider.has(Type)` with `Type in provider`.
- A custom `ServiceProvider` implementation must rename its `get`/`has` methods to
  `__getitem__`/`__contains__` to keep satisfying the protocol (structural — no inheritance
  required, same as before).
- `examples/` migrate post-release via the `example` skill.
