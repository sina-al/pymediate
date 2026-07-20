# ADR 0016: Shrink the ServiceProvider protocol and adopt `Container.traverse()`

**Status:** Accepted (2026-07-20, @sina-al)
**Date:** 2026-07-20
**Author:** Claude
**Context:** Follows #114; supersedes ADR 0012's discovery-mechanism decision
**Reviewers:** @sina-al

## Context

Two decisions land together, both driven by the same fact: after ADR 0015 (#113/#123)
moved pipeline-behavior ordering onto the mediator's explicit `behaviors=` sequence,
`ServiceProvider.get_all()` has **no remaining caller in the library** — the mediator
resolves handlers and behaviors by exact class through `get()`.

1. **`get_all()` is dead public surface.** It was the only protocol method with an
   ordering guarantee and the only one doing inheritance-aware (`isinstance`) resolution.
   Nothing in `src/`, `examples/`, or the typing snippets calls it. #114 originally scoped
   *against* removing it ("the protocol's method signatures do not change"); the maintainer
   overrode that scope: an unused public method is maintenance and comprehension cost with
   no offsetting benefit, and ZeroVer + a negligible user base make the removal cheap.

2. **`DependencyInjectorServiceProvider` discovery was a hand-rolled recursive scan.** ADR
   0012 chose an "ordered recursive declaration scan" over `Container.traverse()`, rejecting
   `traverse()` for two reasons: (a) it does not preserve declaration order, and (b) it walks
   injection-only providers, exposing objects never declared as container attributes. Reason
   (a) is now moot — no provider promises order any more. Reason (b) is a deliberate design
   preference, not a correctness constraint, and `traverse()` is the library's own primitive
   built for exactly this ("visit the whole provider graph"). The maintainer directed adopting
   it and accepted the behavior change.

## Decision

**Remove `get_all()` and `get_all_types()`** from the `ServiceProvider` protocol, the
built-in `_Provider`, and `DependencyInjectorServiceProvider`. Neither has a non-test caller
in the package (`get()`/`has()`/`__len__` cover every internal need: the mediator resolves
by exact class through `get()` and validates behaviors with `has()`; `ServiceNotFoundError`
lists available types from provider internals directly). The protocol shrinks to three
operations: `get`, `has`, `__len__`. `get()` keeps exact-type, first-registered semantics.
`has()` stays because the mediator's behavior validation calls it.

**Both built-in providers now inherit `ServiceProvider` explicitly.** Conformance was only
verified structurally at call sites; inheriting makes a static checker verify it at the class
definition. Custom providers may still conform purely structurally — the protocol is
unchanged in that respect.

**Rewrite DI discovery around `Container.traverse()`.** One walk of the graph replaces the
recursive `_scan_container` and its manual cycle guard (`traverse()` is cycle-safe). The
`_Registration` wrapper is gone — the type→providers dict (a `defaultdict(list)`) is the whole
index, and the dict key is the service type passed to resolution. Type inference
(`_callable_return_type`) and delegation to the original provider for resolution are
unchanged. Consequences accepted deliberately:

- **Un-typeable providers are skipped, not rejected.** Because `traverse()` walks the *whole*
  graph — including infrastructure providers reachable only through injection — a provider
  whose output type cannot be inferred (an unannotated factory, `Selector`, `Resource`, or
  coroutine provider) is simply not indexed, rather than raising at construction. Raising was
  viable when only declared attributes were scanned; with whole-graph traversal it would break
  any container that mixes handlers with an infrastructure `Resource` (it broke the
  `900-hexagonal-architecture` example). A provider that resolves asynchronously is still
  rejected at *resolution* time.
- **Injection-only providers that can be typed are now indexed** as services, resolvable by
  exact type. This is the direct reversal of ADR 0012's reason (b).
- **Container cycles no longer raise;** `traverse()` walks them safely and terminates.
- Resolution-time error messages name the provided class/callable (e.g. `'build_service'`)
  rather than a container attribute path, since traversed providers do not carry their name.
- A type-changing `.override()` yields the overridden and overriding provider both; each is
  indexed by its effective type. `get()` reads the first, which resolves through the
  override, so the harmless duplicate is never observed. No dedup machinery.

This supersedes the "Ordered recursive declaration scan (recommended)" decision in ADR 0012,
along with its construction-time rejection of opaque providers; 0012's type-inference and
resolution-delegation decisions still stand.

## Consequences

### Positive

- The protocol a custom provider must satisfy is smaller (three methods, none with an
  ordering or inheritance-resolution obligation) — a better story for the `120-custom-provider`
  example and anyone implementing `ServiceProvider`.
- The DI adapter drops its recursion and cycle-detection code and uses the library's own
  graph-walk primitive; nested containers and injected providers are reached without a
  bespoke scan.
- No method carries an ordering guarantee, so ordering is a non-question across every
  provider.

### Negative

- **Breaking:** `get_all()` and `get_all_types()` are gone from the `ServiceProvider`
  surface; a caller of `get_all()` must switch to `get()` (exact type) or its own iteration,
  and a caller of `get_all_types()` must track registered types itself. ZeroVer minor.
- **Discovery is broader:** a DI provider used only as an injected dependency now resolves
  as a service. An app that relied on injection-only providers staying invisible sees them
  indexed. Documented in the DI guide.
- **Un-typeable providers fail silently:** a provider intended as a service but not typeable
  (an unannotated factory) is now skipped rather than flagged at construction; the miss
  surfaces as a `ServiceNotFoundError` at resolution instead of an eager error.
- Error messages lost their container-attribute path; they name the provided type instead.

## Migration Path

Breaking change, shipped in a **minor** release (ZeroVer):

- Replace any `provider.get_all(Base)` with `provider.get(ExactType)`, or iterate the
  caller's own collection — inheritance-aware multi-resolution is no longer a provider
  concern.
- No change needed for handler/behavior resolution: the mediator already uses `get()`.
- `examples/` migrate post-release via the `example` skill if any referenced `get_all()`
  (none do today).
