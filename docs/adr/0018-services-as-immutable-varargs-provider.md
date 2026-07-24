# ADR 0018: `Services` becomes a single immutable, varargs-constructed `ServiceProvider`

**Status:** Proposed
**Date:** 2026-07-24
**Author:** Claude
**Reviewers:** @sina-al

## Context

ADRs 0016 and 0017 simplified the `ServiceProvider` *protocol* — first shrinking it to two
operations, then replacing `get()`/`has()` with `__getitem__`/`__contains__` and framing a
provider as "a read-only `Mapping[type, object]`". Neither touched `Services`, the built-in
collection users actually write. It is also the only part of the service layer with **no ADR**:
`add()`, `provider()`, `clear()`, the snapshot semantics, and keying by `type(instance)` were
never designed on the record.

The resulting wiring is a three-step ritual, and it is the shape all 29 examples use:

```python
services = Services()                    # 1. empty mutable builder
services.add(AddTaskHandler(store))      # 2. mutate; return value discarded
services.add(CompleteTaskHandler(store))
return Mediator(services.provider())     # 3. freeze into a different class
```

Four findings make this a defect rather than mere verbosity:

1. **`clear()` has no non-test caller.** Its three call sites were all in `tests/test_service.py`
   testing `clear()` itself. The same held for the snapshot guarantee: mutating a `Services`
   after `provider()` appeared *only* in tests asserting snapshot isolation, while four docs
   pages told users not to do it. `provider()` existed to defend against something nobody did.
2. **ADR 0016 left the per-type `list` unreachable.** `Services` stored
   `dict[type, list[Any]]`, but `__getitem__` always returned `[0]` and `get_all()` was gone —
   so instances 2..n of a type could not be observed by any API. Their only effect was inflating
   `len()`. Dead state, unnoticed when 0016 landed.
3. **`add()` returning `self` is fluent-Java, not Python.** `set.add()` returns `None`. It also
   fought this repo's own quality bar: it is why the typing-snippet rules had to say *"consume
   `Services.add(...)` results by chaining into `.provider()`"* — otherwise basedpyright's
   recommended mode flagged the unused result. All 29 examples discarded it anyway.
4. **`Mediator`'s parameter is already named `services`.** `Mediator(services=services.provider())`
   is the tell: a `Services` had to be converted into something else to be passed to the
   parameter named after it.

`_Provider` additionally duplicated `Services.__len__` and `__repr__` verbatim and reached into
`collection._services` across a class boundary.

## Proposed Solution(s)

### Option A — One immutable class, constructed from its members (RECOMMENDED)

```python
class Services(ServiceProvider):
    def __init__(self, *instances: object) -> None: ...
    def __getitem__[ServiceT](self, service_type: type[ServiceT]) -> ServiceT: ...
    def __contains__(self, service_type: type) -> bool: ...
    def __or__(self, other: Services) -> Services: ...
    def __len__(self) -> int: ...
```

```python
return Mediator(Services(AddTaskHandler(store), CompleteTaskHandler(store)))
```

**Pros:**

- This is the `set(...)`/`dict(...)`/`frozenset(...)` idiom: a collection constructed from its
  members rather than built by mutation. It completes the frame ADR 0017 locked in — if a
  provider *is* a read-only `Mapping[type, object]`, it should be built like one.
- The immutability guarantee stops being documented prose and becomes structural: there is no
  mutator to defend against, so the snapshot concept disappears rather than being maintained.
- Two classes collapse to one; `service.py` goes from 248 to ~160 lines with more capability.
- Verified before implementation, not assumed: `services[Foo]` still infers `Foo` (not `Any`)
  under both `mypy --strict` and basedpyright, and `wrong: int = services[Foo]` is flagged by
  both — the exact-type inference ADR 0017 secured carries over unchanged.

**Cons:**

- Breaking, with the widest blast radius of the three service ADRs: every wiring in `examples/`,
  every typing snippet, ~15 docs pages, and the README.
- Registering services computed at runtime requires unpacking (`Services(*handlers)`) rather
  than a loop. Acceptable — no example in the repo loops over services today.

### Option B — Keep the builder, add the dunders to it (rejected)

Leave `add()`/`provider()`/`clear()` in place and additionally implement `__getitem__`/
`__contains__` on `Services` so it can be passed directly.

**Pros:** Non-breaking; the one-liner ergonomics arrive without touching any call site.

**Cons:** The class becomes a *mutable* provider, which is strictly worse than either end of the
trade-off: a mediator holds its provider for life and re-resolves on every dispatch, so a later
`add()` would silently change dispatch behaviour long after construction. It also keeps two ways
to do one thing forever — the "parallel APIs for one operation" ADR 0017 explicitly rejected.

### Option C — Subclass `collections.abc.Mapping` (rejected)

**Cons, decisive:** `Mapping.__getitem__` returns the value type, so overriding it with
`type[ServiceT] -> ServiceT` is an LSP violation `mypy --strict` flags — it would destroy the
exact-type inference ADR 0017 verified. It also re-imports `.get()`, `.keys()`, `.items()` and
`__eq__` into the surface ADR 0016 deliberately shrank, and `Mapping.__contains__` accepts
`object` rather than `type`. The mapping *frame* is right; the mapping *ABC* is not.

## Decision

**Option A.** Three sub-decisions were taken with the maintainer (2026-07-24):

- **A repeated type raises**, rather than first-wins (today's behaviour) or last-wins (dict's).
  `Services(GetUserHandler(a), GetUserHandler(b))` raises the new
  `ServiceAlreadyRegisteredError`, because only one instance per type is ever resolvable, so a
  repeat is a wiring bug. This follows the repo's existing culture rather than dict's: the
  handler registry raises `HandlerAlreadyRegisteredError` for two handler classes on one request
  type, and `_validate_behaviors` already raises `InvalidPipelineBehaviorsError(entry, "listed
  more than once in the behaviors sequence")` for a duplicate in `behaviors=` — itself a
  varargs-style sequence. Silently dropping an instance the caller constructed is the one
  outcome none of those precedents allow.
- **The name stays `Services`.** `Services(a, b, c)` reads like `set(...)`, and `Mediator`'s
  parameter is already `services`. `Container` collides with dependency-injector's
  `containers.Container`, which PyMediate adapts; `Registry` collides with the internal handler
  registry in `_internal/registry.py`; `Provider` collides with `providers.*`.
- **`|` combines two collections, right operand winning**, mirroring PEP 584's `dict.__or__`.
  Both operands are left unchanged. A shared type is *not* an error here — that is the operator's
  purpose, which resolves the tension with raising in the constructor: replacing a service
  becomes explicit rather than positional. `|` is a concrete convenience on `Services`, **not**
  a protocol member — same status `__len__` has under ADR 0016, so no custom `ServiceProvider`
  is obliged to implement it. There is no `__ior__`: `services |= other` rebinds, as for a tuple.

`ServiceNotFoundError` is unchanged, including ADR 0017's `KeyError` base and `__str__`
override. `ServiceAlreadyRegisteredError` inherits `PyMediateError` and lives in `errors.py` with
the other wiring errors — it is a declaration mistake, not a failed lookup, so 0017's separation
between the two families is preserved.

## Consequences

### Positive

- One class instead of two, and one obvious way to wire an application. The `_Provider`/`Services`
  code duplication (`__len__`, `__repr__`, cross-class private access) is gone.
- The dead per-type instance lists left by ADR 0016 are deleted; `len()` can no longer disagree
  with the number of resolvable services.
- A silent failure mode became loud: two instances of one type used to mean the second was
  quietly unreachable, and now raises at construction.
- Overriding a service for a test is a supported one-liner
  (`build_services() | Services(FakeStore())`) instead of rebuilding a wiring by hand.
- `Services` is a better model for the planned `120-custom-provider` example (issue #90) — the
  built-in provider is now the same shape a custom one would take.
- `__repr__` became `Services(ServiceA, ServiceB)`, the constructor call that would rebuild it,
  rather than a `total=`/per-type-count summary that can no longer vary.

### Negative

- **Breaking**, on a surface CI flags: `Services`' signature changes and `__all__` gains
  `ServiceAlreadyRegisteredError`. ZeroVer minor.
- Callers registering a computed set of services must unpack (`Services(*instances)`); a
  conditional wiring builds its list first rather than calling `add()` in a branch.
- `Services()` no longer defends a mediator against later mutation *because the mutation is
  impossible* — but a custom `ServiceProvider` may still be mutable, so the "thread-safety and
  mutation behavior depend on the implementation" note stays on the protocol.

### Correction to ADRs 0016 and 0017

Both state that `examples/` are not updated by their implementing change because examples pin the
*released* package and migrate post-release. **That is wrong, and it broke CI on PR #137.**
`pr.yml`/`checks.yml`'s `Run Examples` job is a required check that builds a wheel from the branch
under test and runs every example against it, so an example using a removed API fails the PR that
removes it. Examples are in scope for any breaking change, in the same commit. This ADR's
implementation updates all 29 wirings, and the claim should not be repeated in a future ADR.

## Migration Path

Breaking change, shipped in a **minor** release (ZeroVer):

- `Services().add(a).add(b).provider()` → `Services(a, b)`.
- The builder form (`s = Services()`, then `s.add(...)` per line, then `Mediator(s.provider())`)
  → one `Services(...)` call passed straight to `Mediator`.
- `provider()` and `clear()` are gone. A `Services` *is* a `ServiceProvider`; to "clear", build a
  new collection.
- Registering two instances of one type now raises instead of silently keeping the first. If the
  intent was replacement, use `left | right`; if both must be resolvable, give them distinct
  types.
- A custom `ServiceProvider` is unaffected — the protocol does not change.

## Open Questions

- Should `Services` accept an iterable as well as varargs (`Services([a, b])`)? Left out
  deliberately: a service that is itself iterable would make the two forms ambiguous, and
  `Services(*instances)` already covers the computed case. Tentative lean: keep varargs-only
  unless a real wiring finds it awkward.
- `ServiceAlreadyRegisteredError` currently carries only `service_type`. Should it also carry the
  two colliding instances? Lean no — their `repr()` may be large and the type is what identifies
  the mistake — but a debugging case could justify adding them later (additive, non-breaking).
