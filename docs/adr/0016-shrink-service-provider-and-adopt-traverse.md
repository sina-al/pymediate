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

**Remove `get_all()`** from the `ServiceProvider` protocol, the built-in `_Provider`, and
`DependencyInjectorServiceProvider`. The protocol shrinks to four operations: `get`, `has`,
`get_all_types`, `__len__`. `get()` keeps exact-type, first-registered semantics.

**Rewrite DI discovery around `Container.traverse()`.** One walk of the graph replaces the
recursive `_scan_container` and its manual cycle guard (`traverse()` is cycle-safe). Type
inference (`_service_type` / `_callable_return_type`), opaque/async rejection, and
delegation to the original provider for resolution are unchanged. Consequences accepted
deliberately:

- **Injection-only providers are now indexed** as services, resolvable by exact type. This
  is the direct reversal of ADR 0012's reason (b).
- **Container cycles no longer raise;** `traverse()` walks them safely and terminates.
- **Provider error messages name the provided class/callable** (e.g. `'build_service'`)
  rather than a container attribute path, since traversed providers do not carry their
  attribute name. Acceptable degradation for a much simpler walk.
- A type-changing `.override()` yields the overridden and overriding provider both; each is
  indexed by its effective type. `get()` reads the first, which resolves through the
  override, so the harmless duplicate is never observed. No dedup machinery.

This supersedes the "Ordered recursive declaration scan (recommended)" decision in ADR 0012;
0012's type-inference and resolution-delegation decisions still stand.

## Consequences

### Positive

- The protocol a custom provider must satisfy is smaller (four methods, none with an
  ordering or inheritance-resolution obligation) — a better story for the `120-custom-provider`
  example and anyone implementing `ServiceProvider`.
- The DI adapter drops its recursion and cycle-detection code and uses the library's own
  graph-walk primitive; nested containers and injected providers are reached without a
  bespoke scan.
- No method carries an ordering guarantee, so ordering is a non-question across every
  provider.

### Negative

- **Breaking:** `get_all()` is gone from `__all__`'s `ServiceProvider` surface; any caller
  must switch to `get()` (exact type) or their own iteration. ZeroVer minor.
- **Discovery is broader:** a DI provider used only as an injected dependency now resolves
  as a service. An app that relied on injection-only providers staying invisible sees them
  indexed. Documented in the DI guide.
- Error messages lost their container-attribute path; they name the provided type instead.

## Migration Path

Breaking change, shipped in a **minor** release (ZeroVer):

- Replace any `provider.get_all(Base)` with `provider.get(ExactType)`, or iterate the
  caller's own collection — inheritance-aware multi-resolution is no longer a provider
  concern.
- No change needed for handler/behavior resolution: the mediator already uses `get()`.
- `examples/` migrate post-release via the `example` skill if any referenced `get_all()`
  (none do today).
