# ADR 0015: Mediator-owned pipeline behavior order

**Status:** Accepted (2026-07-18, @sina-al)
**Date:** 2026-07-18
**Author:** Claude
**Context:** Supersedes the rejected ADR 0014 for issue #113
**Reviewers:** @sina-al

## Context

ADR 0014 proposed making pipeline behavior order an explicit `order: int` class
attribute on every concrete `PipelineBehavior` subclass, validated by the mediator. It
was **rejected** (2026-07-18): sort order is a property of a *specific application's*
composition of behaviors, not intrinsic to a behavior class. A class-level key forces
every behavior author — including third parties packaging a reusable behavior — to bake
in an ordering opinion. A consumer who disagrees has only one recourse: subclass purely
to override an integer.

```python
# ADR 0014's rejected shape - a third-party behavior ships its own opinion:
class RateLimiting(PipelineBehavior[Request[Any]]):
    order = -50  # whose call is this, the library author's or the app's?
```

The underlying problem ADR 0014 was solving is still real and still issue #113's:
execution order today is whatever `ServiceProvider.get_all(PipelineBehavior)` happens to
return, backed only by unenforced docstring prose ("registration order is execution
order"), so a custom provider or a `dependency-injector` container refactor can silently
reorder the pipeline. This ADR proposes a mechanism for the same problem that keeps
ordering where it belongs: the composition root, not the behavior class.

## Proposed Solution(s)

### Option A: Ordered `behaviors=` sequence on the mediator (RECOMMENDED)

The mediator constructor accepts an explicit, ordered sequence of behavior *classes*.
The sequence **is** the order — first entry outermost, exactly like today's chain
composition, but now declared once at the one place that actually owns "what pipeline
does this application run," instead of inferred from provider iteration.

```python
class RequestLogging(PipelineBehavior[Request[Any]]):
    async def __call__(self, request: Request[Any], next: Next[Any]) -> Any:
        return await next()

class Auth(PipelineBehavior[Request[Any]]):
    def __init__(self, token_service: TokenService) -> None:
        self._tokens = token_service

    async def __call__(self, request: Request[Any], next: Next[Any]) -> Any:
        self._tokens.check()
        return await next()

services = (
    Services()
    .add(TokenService())
    .add(RequestLogging())
    .add(Auth(TokenService()))
)

mediator = Mediator(
    services=services.provider(),
    behaviors=[RequestLogging, Auth],  # order lives here, not on the classes
)
```

Resolution mechanics, identical for every `ServiceProvider` implementation:

- **At construction**, the mediator validates the list once: every entry must be a
  `PipelineBehavior` subclass of the correct sync/async variant, and resolvable —
  `provider.has(cls)` for the built-in provider's exact-type registration, or an
  equivalent existence check for a custom provider. A duplicate class in the list, or an
  unregistered one, raises immediately, naming the offending entry — this is a hard
  requirement, not a should: `Mediator(services=provider, behaviors=[Auth])` where
  `Auth` was never registered with `provider` must fail at `Mediator(...)` itself,
  never lazily at first `send()`. Deferring it to dispatch would resurrect the same
  late-failure mode ADR 0014's dispatch-time option was rejected for.
- **Per dispatch**, `_resolve_behaviors` walks `behaviors` in order, calls
  `should_apply(request)` on each (unchanged - selection stays dynamic, per ADR 0003),
  and resolves the applicable ones via `provider.get(cls)` - so DI lifetimes are
  untouched: `Factory` still builds a fresh instance per resolution, `Singleton` still
  shares one. Nothing is cached by the mediator, preserving ADR 0003's lifetime
  invariant.
- **`ServiceProvider.get_all()` is never called for behaviors.** The provider's role
  shrinks to "resolve this class to an instance" - `get()`, not `get_all()`. This is the
  sole `get_all(PipelineBehavior)` call site in the library (`_internal/mediator.py:102`
  today), so removing it fully unblocks #114: nothing left consumes `get_all()`'s
  sequence for anything semantic, in any provider.
- Behaviors registered in the provider but **absent from the list are simply not part of
  the pipeline** - the provider is a resolution mechanism, not a manifest. This also
  fixes a latent oddity in the current design: today, registering *any*
  `PipelineBehavior` anywhere in the provider silently joins every mediator's pipeline
  that shares it; explicit listing makes membership as deliberate as order.

**DI provider - identical shape, only the container differs:**

```python
class AppContainer(containers.DeclarativeContainer):
    token_service = providers.Singleton(TokenService)
    # Attribute order is now cosmetic - reordering this class body no longer
    # touches the pipeline.
    auth = providers.Factory(Auth, token_service=token_service)
    request_logging = providers.Singleton(RequestLogging)

mediator = Mediator(
    services=DependencyInjectorServiceProvider(AppContainer()),
    behaviors=[RequestLogging, Auth],
)
```

**Pros:**

- The rejected design's core problem disappears entirely, not just mitigated: no class
  anywhere carries an ordering opinion, so a third-party behavior ships inert and its
  consumer places it with zero subclassing.
- One declaration to read for "what is this application's pipeline, in what order" -
  more legible than tracing `order` values scattered across N class definitions plus a
  strictness-mode setting.
- Deletes the entire strictness-mode question (`relaxed`/`unique`) - a Python sequence
  cannot have "duplicate positions" the way scattered integers can collide; if an app
  genuinely wants two behaviors unordered relative to each other, nothing stops
  composing them as one combined behavior, which is arguably the more honest expression
  of "run these together."
- Construction-time validation is *cheaper* than ADR 0014's: `has()`/existence checks,
  no eager `get_all()` scan, no DI `Factory` pre-instantiation. The DI eager-resolution
  concern from ADR 0014 disappears.
- Fully retires `get_all()`'s ordering role - #114 can proceed without the wording
  reconciliation ADR 0014 required, since there is no relaxed-mode tie behavior left to
  reconcile.
- Enables per-mediator pipelines over one shared provider (e.g. an internal mediator
  that skips `Auth`) - not achievable by a class-level key at all.

**Cons:**

- **No auto-discovery.** Registering a `PipelineBehavior` instance no longer
  automatically joins any pipeline; the app must enumerate every behavior it wants to
  run. This is a deliberate trade, not an oversight - see "Constraints & non-goals."
- **Breaking, differently shaped than ADR 0014's.** Existing code that relies on
  provider-registration order (rather than an explicit list) must add the `behaviors=`
  argument at every `Mediator(...)` call site - a migration that touches call sites
  instead of class bodies. For an application with one composition root this is a
  single-line change; for one with many mediator constructions it is proportionally
  larger, but still mechanical (see Migration Path).
- The mediator's constructor grows a new keyword-only parameter on both variants -
  shared shape, mirrored per the sync/async parity contract.
- A behavior class must still be *registered* with the provider (so it can be
  resolved by `get()`) *and* listed in `behaviors=` - two places name it, though only
  one (`behaviors=`) encodes order. This is inherent to keeping resolution and ordering
  separated; not eliminable without collapsing the distinction, which would reintroduce
  a coupling this design deliberately avoids (see Option C below).

### Option B: `order=` mapping on the mediator

`Mediator(services=provider, behaviors={RequestLogging: -100, Auth: 10})` - keep
`get_all()`-based discovery for *membership* (every registered `PipelineBehavior`
still auto-joins the pipeline), but let the app override each one's numeric position via
a dict at construction; unmapped registered behaviors get an error, or a defined default
ordering (e.g. declaration order, or last).

**Pros:**

- Preserves auto-discovery - a newly registered behavior needs a positional entry but
  not a re-declared list of everything.
- Solves the third-party objection: the app assigns the number, not the library.

**Cons:**

- Keeps the worst ergonomics of the rejected design - arbitrary integers, gap-numbering
  conventions (`-100`, `10`, ...) revived one level up, harder to scan than a list's
  left-to-right order.
- Still needs a decision for unmapped-but-registered behaviors (silently last? error?
  warn?) - reintroduces a strictness-mode-shaped question the list design deletes
  outright.
- Auto-discovery is exactly the implicitness issue #113 exists to remove; keeping it
  for membership while fixing only the ordering half is a partial fix.
- Rejected: strictly more moving parts than Option A for no benefit A doesn't already
  provide.

### Option C: Instance-level order at registration (`ordered()` wrapper)

`services.add(ordered(RequestLogging(), position=-100))`, or a mediator-recognized
instance attribute set at registration time - order attaches to the *registered
instance*, not the class, keeping `get_all()`-based discovery.

**Pros:**

- Application-owned, like Option A - no class carries an opinion.
- No new mediator constructor parameter; the existing `services.add()` chain expresses
  order too.

**Cons:**

- Scatters ordering across N `.add()` calls in the composition root instead of
  centralizing it in one readable sequence - the same "hard to see the whole pipeline at
  a glance" complaint that (partly) motivated moving away from pure registration order
  in the first place.
- Needs a new public helper (`ordered()`) or a provider-specific mechanism for setting
  an attribute the DI provider's declarative containers don't naturally express (a
  `providers.Factory` doesn't have an obvious place to hang a positional integer without
  its own wrapper).
- Still needs a numeric (or comparable) key, so still needs the
  unique-vs-not-unique question.
- Rejected: Option A achieves the same ownership shift with less new surface and better
  readability.

## Decision

Option A: an explicit, ordered `behaviors: Sequence[type[PipelineBehavior]] | None = None`
keyword-only parameter on `MediatorMixin.__init__` (shared by both async and sync
mediators). Omitted or `None` means **an empty pipeline** — no behaviors run, regardless
of what is registered with the provider. There is no fallback to `get_all()`-based
registration order at any point, not even transiently: a fallback would resurrect, for
the single most common call site (an app that hasn't added `behaviors=` yet), the exact
silent-misordering failure this redesign exists to remove. A vanished pipeline fails
loudly and immediately (an auth check that stops running breaks a test); a silently
reordered one does not.

Rationale:

- It is the only option where the rejected design's actual objection - ordering opinions
  living on the wrong object - disappears rather than being patched. Options B and C
  keep some form of numeric key or partial auto-discovery and inherit a shrunk version
  of the same tension.
- It fully retires `get_all()`'s use for behavior ordering, which strengthens rather than
  complicates #114 (no relaxed-mode wording to reconcile, no tie-breaking semantics to
  define).
- It is the cheapest to validate: existence checks against the provider, no eager
  resolution, no DI `Factory` pre-instantiation consequence to document and accept.

## Consequences

### Positive

- No behavior class, first- or third-party, ever encodes an ordering opinion.
- The pipeline for a given mediator is legible as one ordered list at its construction
  site, not reconstructed by tracing registration calls or class attributes.
- `get_all(PipelineBehavior)` has no remaining callers in the library once this lands -
  #114 can proceed with a strictly simpler mandate (retire the ordering promise with no
  relaxed-mode semantics to preserve).
- A deliberately misbehaving `ServiceProvider` whose `get_all()` returns matches shuffled
  is now irrelevant to behavior ordering by construction, not merely tested-and-verified
  as with ADR 0014's approach - `get_all()` isn't in the ordering path at all.
- Supports multiple differently-ordered (or differently-scoped) pipelines over one
  shared provider.

### Negative

- **Breaking**, at every `Mediator(...)` call site that currently relies on registration
  order for more than one applicable behavior - must add `behaviors=[...]`. ZeroVer
  minor.
- Auto-discovery of registered behaviors is gone. An app that registers a behavior but
  forgets to list it silently runs a pipeline missing that behavior - the inverse
  failure mode of ADR 0014 (which failed loudly on a missing `order`). This ADR's
  construction-time validation only checks that *listed* classes resolve; it cannot
  detect an unlisted-but-registered behavior, because "not everything registered belongs
  in this pipeline" is the design's premise, not a bug. Mitigated in docs/guide with an
  explicit callout; a possible future lint-level warning (registered `PipelineBehavior`
  instances not referenced by any constructed mediator's `behaviors=`) is left as an
  open question, not a commitment.
- Two places name a behavior class (provider registration + `behaviors=` list) where
  before there was one; a typo'd or renamed class must be updated in both.

## Migration Path

Breaking change, shipped in a **minor** release (ZeroVer):

1. Add `behaviors: Sequence[type[PipelineBehavior]] | None = None` (or the async/sync
   equivalent type) to `MediatorMixin.__init__`; both mediators inherit it unchanged
   per the parity contract.
2. `_resolve_behaviors` (`_internal/mediator.py`) stops calling
   `self._services.get_all(pipeline_behavior_type)` and instead walks the mediator's
   stored `behaviors` sequence, resolving each via `provider.get(cls)` and filtering by
   `should_apply`.
3. Construction-time validation: every class in `behaviors` must subclass the mediator
   variant's `PipelineBehavior`, must be resolvable via the provider, and must not repeat
   - each checked once, at `Mediator(...)`.
4. Every call site across tests, typing snippets, docstring examples, and `docs/`
   that registers more than one applicable behavior and relies on registration order
   gains an explicit `behaviors=[...]` - found by the implementation-time sweep this
   issue already mandates, not enumerated here.
5. The pipeline-behaviors guide's "Register and order behaviors" section is rewritten
   around `behaviors=`; the `ServiceProvider` protocol docstring's "registration order"
   promise is removed (coordinate with #114, which now has a strictly smaller job: no
   relaxed-mode wording to keep consistent).
6. `examples/` migrate post-release via the `example` skill, tracked as #113's existing
   final phase.

## Open Questions

- **Should there be a lint-level affordance for "registered but never listed"
  behaviors** (a common mistake this design newly permits) - e.g. an opt-in debug check,
  or nothing beyond documentation? Lean: nothing built-in initially; revisit if it proves
  a frequent footgun in practice.
- **Parameter name**: `behaviors` reads naturally at the call site
  (`Mediator(services=..., behaviors=[...])`) but is a slightly generic noun next to
  `services`. Alternatives considered: `pipeline` (implies more than a plain sequence),
  `behavior_order` (verbose, redundant with the parameter's evident purpose). Lean:
  keep `behaviors`.
