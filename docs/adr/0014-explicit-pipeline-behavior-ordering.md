# ADR 0014: Explicit, provider-independent pipeline behavior ordering

**Status:** Proposed
**Date:** 2026-07-18
**Author:** Claude
**Reviewers:** @sina-al

Implements the design phase of issue #113.

## Context

Pipeline behavior execution order is currently whatever sequence
`ServiceProvider.get_all(PipelineBehavior)` happens to return. The mediator resolves the
registered behaviors, filters them with `should_apply()`, and composes the chain in that
sequence — first item outermost (`_internal/mediator.py`'s `_resolve_behaviors`,
`_internal/pipeline.py`'s `compose`/`compose_async`). The ordering guarantee exists only
as docstring prose on the `ServiceProvider` protocol ("returning all matches in
registration order") and as a line in the pipeline-behaviors guide ("Registration order
is the execution order"). Nothing in the protocol's type surface or at runtime enforces
it.

```python
# Today: order is a side effect of registration order in the provider.
services = Services().add(LoggingBehavior()).add(AuthBehavior())
# LoggingBehavior is outermost... as long as the provider honors the prose contract.
```

Three concrete failure modes:

1. **A custom provider can silently reorder the middleware pipeline.** A `Protocol` has
   no way to enforce a sequencing contract on implementations; a provider that returns
   `get_all()` matches in, say, first-resolution order or hash order type-checks and runs
   without complaint — the pipeline just executes in the wrong order.
2. **For `DependencyInjectorServiceProvider`, "registration order" means container
   attribute declaration order.** An innocent refactor that reorders class attributes in
   a container silently reorders the pipeline.
3. **Selective behaviors stretch the convention past usability.** The relative order of
   two behaviors that apply to the same request can be determined by registrations far
   apart in the composition root, interleaved with behaviors that don't apply at all.

The sibling issue #114 will retire the ordering promise from `ServiceProvider.get_all()`
entirely once nothing consumes it — so this design must not lean on provider order for
anything semantic.

## Proposed Solution(s)

The mechanism itself is locked by issue #113: a **mandatory integer order key declared on
every concrete `PipelineBehavior` subclass**; the mediator sorts applicable behaviors by
it before composing the chain; lower values run outermost. Mandatory is a deliberate
breaking change — silent implicit ordering is the bug being removed, and an optional key
with a default reintroduces it for every behavior that omits the key.

```python
# Proposed API (sketch — does not run against the released package):
class LoggingBehavior(PipelineBehavior[Request[Any]]):
    order = -100  # outermost

    async def __call__(self, request: Request[Any], next: Next[Any]) -> Any:
        return await next()

class AuthBehavior(PipelineBehavior[Request[Any]]):
    order = 10

    async def __call__(self, request: Request[Any], next: Next[Any]) -> Any:
        return await next()

# Registration order no longer matters:
services = Services().add(AuthBehavior()).add(LoggingBehavior())
mediator = Mediator(services=services.provider())  # validates behaviors here
```

What this ADR decides is everything the issue delegated: the enforcement point, the
strictness modes and their API shape, and the key's shape and name.

### Enforcement point

#### Option A: Validate at `Mediator` construction (RECOMMENDED)

`MediatorMixin.__init__` calls `self._services.get_all(PipelineBehavior)` (the variant's
own behavior base) once, eagerly, and validates the resolved set: every instance's class
must declare an order key, and — in unique mode — no two classes may share one. Any
violation raises at `Mediator(...)`, before the first dispatch.

**Pros:**

- Fails at composition time, in the composition root, naming the offending classes —
  exactly where the person wiring the application can fix it.
- The mediator is the component that *consumes* the order, so it is the natural place to
  validate it; no provider cooperation required, which is the point (a `Protocol` cannot
  be policed — see Option D).
- Uniqueness is checkable at all: it is a property of the *registered set*, which only
  exists once a provider is handed to a mediator.

**Cons:**

- **Eager instance resolution.** For the built-in `Services`/`_Provider`, `get_all()`
  returns already-constructed instances — no observable change. For
  `DependencyInjectorServiceProvider`, `get_all()` *resolves* every matching provider, so
  DI-managed behaviors are instantiated at mediator construction rather than first
  dispatch (`Factory`-provided behaviors get built once extra), and its
  protocol-fallback branch can resolve non-behavior services while testing `isinstance`.
  Validation inspects only `type(instance)` class attributes and discards the instances —
  per ADR 0003's lifetime invariant, the mediator must not cache them — so per-dispatch
  resolution semantics are unchanged. This cost is accepted and documented: construction
  is a one-time event, and a behavior whose *instantiation* has side effects heavy enough
  to matter is already fragile under `Factory` lifetimes.
- A behavior class defined and registered *after* the mediator is constructed escapes
  validation until dispatch. Mitigated: providers are immutable snapshots
  (`Services.provider()` copies; the DI provider indexes at construction), so the
  registered set cannot grow after the mediator sees it. The sort itself still happens
  per dispatch (see "Sorting" below), so even a hypothetical mutable provider gets
  correct ordering — only the *loud* validation is front-loaded.

#### Option B: Validate at dispatch time

Check order keys inside `_resolve_behaviors`, on every `send()`.

**Pros:**

- No eager resolution; zero construction-time cost.
- Catches even behaviors from a (hypothetical) mutable provider.

**Cons:**

- Fails late — a misconfigured behavior that only applies to a rarely-sent request type
  raises in production on first hit, which is precisely the silent-until-it-matters
  failure mode this design exists to kill.
- Per-dispatch validation cost on the hot path ADR 0003 just spent effort thinning.
- Rejected.

#### Option C: Enforce at class definition via `__init_subclass__`

`PipelineBehavior.__init_subclass__` already runs per subclass (it caches
`__request_type__`); it could also require the order key, raising at `class` statement
time.

**Pros:**

- Earliest possible failure — the class doesn't even come into existence unordered.
- No provider interaction, no eager resolution.

**Cons:**

- **Cannot check uniqueness.** Class definition sees one class at a time; duplicate keys
  are a property of the registered set, so a second enforcement point would still be
  needed — this can only ever be a supplement, not the mechanism.
- **Cannot distinguish concrete behaviors from reusable intermediates.** A generic
  reusable layer (`class Retry[RequestT: Request[Any]](PipelineBehavior[RequestT])`) or
  an abstract intermediate legitimately declares no order; detecting "concrete" via
  `__abstractmethods__` is fragile (an intermediate that implements `__call__` but is
  never registered directly would be forced to carry a meaningless key).
- Rejected as the enforcement point. Left open as a possible future hardening layer for
  the presence check only, if the concrete-detection problem finds a clean answer.

#### Option D: Provider-side enforcement

Make providers responsible for rejecting unordered behaviors at registration.

**Cons (fatal):**

- `ServiceProvider` is a `Protocol` with no registration-time hook — registration isn't
  even part of the protocol, only resolution is. Custom implementations cannot be made
  to validate anything.
- Would push ordering knowledge *into* the provider — the exact coupling this design
  removes.
- Rejected.

### Strictness modes

Two modes, configured per mediator. What is validated in both: every resolved behavior
class declares an order key. What differs: the treatment of duplicate keys.

- **relaxed (DEFAULT):** duplicate keys are allowed and mean the author doesn't care
  about the relative order of the tied behaviors — a legitimate, explicitly-declared
  statement of indifference (two independent metrics collectors, say). Tied behaviors
  each run exactly once, in an **unspecified but deterministic** order (implementation:
  a stable sort over the sequence the provider returned). The tie order is deliberately
  *not* documented as registration order — that wording would resurrect the provider
  ordering contract #114 retires.
- **unique:** any two registered behaviors (within the mediator's variant) sharing a key
  is a construction-time error. For teams that want every pipeline totally ordered on
  paper.

Default rationale: the bug being removed is *accidental, invisible* ordering. A
duplicated explicit key is neither accidental nor invisible — the author typed the same
number twice. Making `unique` the default would turn a legitimate "I don't care" into a
construction error and force artificial key invention; strictness should be opt-in.

No third mode is warranted. A "warn" mode was considered and rejected: warnings on
construction are noise that CI ignores and production logs bury; the two modes cover
"total order required" and "partial order sufficient", which exhausts the semantics.

**API shape:** a keyword-only boolean on both mediators' `__init__`:

```python
Mediator(services=provider)                              # relaxed (default)
Mediator(services=provider, unique_behavior_order=True)  # unique
```

An enum (`OrderValidation.RELAXED/UNIQUE`) was considered and rejected: two modes don't
justify a new public name in `__all__`, and the flag reads clearly at the call site. The
accepted cost: if a third mode ever becomes necessary (none is foreseen — see above),
this bool becomes a deprecation. `MediatorMixin.__init__` grows the parameter once,
shared by both variants.

### Key shape and name

- **Name: `order`.** Short, reads naturally at the class-attribute site
  (`order = -100`), matches the vocabulary the guide already uses. `sort_key` describes
  the mechanism, not the meaning; `priority` is ambiguous about direction (is high
  priority outermost or innermost?).
- **Type: plain `int`**, negative values allowed, no magnitude restrictions. Declared on
  the base class as `order: ClassVar[int]` *without* a value — subclasses assign it.
  `bool` is an `int` subclass and would be accepted; not worth guarding against.
- **Direction: lower runs outermost** — consistent with "first is outermost" in the
  existing chain composition, and with the convention that negative numbers push toward
  the edges (framework-ish concerns like logging at `-100`, domain concerns near `0`).
- **Inheritance counts as declaration.** A subclass of a concrete ordered behavior
  inherits its `order` (ordinary attribute lookup); the presence check is effectively
  `hasattr(behavior_cls, "order")` on `type(instance)`. An inherited key is still an
  explicit authorial decision — the parent's author made it.
- The presence check happens only for *registered* behaviors at mediator construction
  (per Option A), so unregistered reusable intermediates never need a key.
- Static enforcement is not attempted: no type-checker mechanism can require subclasses
  to assign a `ClassVar` (that would need something like a `Final` abstract attribute,
  which doesn't exist). Enforcement is runtime-only, which Option A makes loud and early.

### Sorting

`_resolve_behaviors` sorts *after* filtering by `should_apply()`:

```python
applicable = [b for b in all_behaviors if type(b).should_apply(request)]
applicable.sort(key=lambda b: type(b).order)  # stable → deterministic ties
```

Sorting stays per-dispatch (selection is dynamic — ADR 0003's invariant that
`should_apply` can gate on runtime state — and instances can't be cached), but it is
`O(k log k)` over the handful of applicable behaviors, negligible next to the resolution
scan. Validation, being per-set rather than per-request, runs once at construction.

### Error reporting

A new public exception, `InvalidPipelineBehaviorOrderError(PyMediateError)`, raised at
mediator construction for both violation kinds:

- Missing key: names the behavior class and shows the one-line fix
  (`order = <int>  # lower runs outermost`).
- Duplicate key in unique mode: names both classes and the shared value.

It joins `__all__` in both namespaces (identical object, per the parity contract — it is
not async/sync-variant-specific). Growing `__all__` is a flagged surface; the release is
already **minor** for the breaking change itself.

## Decision

- **Enforcement:** Option A — eager validation in `MediatorMixin.__init__`, shared by
  both mediators. The DI provider's eager-instantiation consequence is accepted and
  documented in the DI provider's docs.
- **Modes:** `relaxed` (default) and `unique`, selected by a keyword-only
  `unique_behavior_order: bool = False` on the mediator constructor. Relaxed ties are
  unspecified-but-deterministic, never documented as registration order.
- **Key:** mandatory `order: int` class attribute on every registered concrete behavior,
  lower = outermost, inheritance counts, runtime-enforced only.
- **Error:** new `InvalidPipelineBehaviorOrderError` in `pymediate.errors`, exported from
  both namespaces.

Rationale in brief: validation belongs where the order is consumed and where the full
registered set first exists (the mediator); the default should punish accidents (missing
keys) but not explicit indifference (duplicate keys); and nothing in the design may lean
on provider sequencing, so #114 can retire that contract without touching this one.

## Consequences

### Positive

- Execution order becomes a property of the behaviors themselves — readable at the class
  definition, immune to provider implementation, registration shuffling, or container
  attribute refactors.
- Misconfiguration fails at `Mediator(...)` with the offending class named, not at some
  later dispatch.
- A deliberately misbehaving provider whose `get_all()` returns matches shuffled still
  yields the correct execution order — testable, and tested.
- Unblocks #114: after this, nothing consumes `get_all()`'s sequence semantically.

### Negative

- **Breaking:** every existing concrete behavior — user code, tests, typing snippets,
  docs examples, `examples/` — must add `order`. Accepted deliberately; ZeroVer minor.
- DI-managed behaviors are instantiated once at mediator construction (eager
  `get_all()`); `Factory`-provided behaviors get one extra construction over their
  lifetime, and construction-time side effects in behavior `__init__`s move earlier.
- Two behaviors that never co-apply to any request still collide in unique mode —
  uniqueness is checked per registered set, not per request pipeline. Acceptable: unique
  mode is opt-in and means what it says.
- One more concept to teach in the first pipeline-behaviors example (`order = 0` in the
  minimal case).

## Migration Path

Breaking change, shipped in a **minor** release (ZeroVer):

1. Add `order: ClassVar[int]` (undeclared) to both `PipelineBehavior` variants; mediator
   validation + sorting as above.
2. Every concrete behavior in the repo (tests, typing snippets, docstring examples, docs
   guide) gains an explicit `order` — found by the implementation-time sweep mandated in
   #113, not by any list frozen here.
3. Docs: the pipeline-behaviors guide's "Register and order behaviors" section teaches
   the order key and the two modes; provider order is demoted to an unspecified
   relaxed-mode tie-break. The `ServiceProvider` docstring example fix is reconciled
   with #114's contract retreat (whichever lands second keeps them consistent).
4. `examples/` migrate post-release via the `example` skill (they build against the
   released package), tracked as #113's final phase.
5. User migration is one line per behavior class; the
   `InvalidPipelineBehaviorOrderError` message contains the fix.

## Open Questions

- Is `unique_behavior_order` the right parameter name, or is something shorter
  (`strict_order`?) preferable? Lean: keep `unique_behavior_order` — it says which
  property is enforced and on what, at the cost of length.
- Should the presence check *also* run in `__init_subclass__` for unambiguously concrete
  subclasses (non-abstract, non-generic) as a fast-fail supplement? Lean: no for now —
  two enforcement points for one rule invites drift, and Option A already fails before
  first dispatch.
