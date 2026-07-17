# ADR 0012: Dependency Injector container discovery

**Status:** Accepted
**Date:** 2026-07-17
**Author:** Codex
**Reviewers:** @sina-al

## Context

`DependencyInjectorServiceProvider` adapts the optional `dependency-injector` integration to
PyMediate's synchronous `ServiceProvider` protocol. The original implementation accepted a
`containers.Container`, iterated its direct `providers` mapping, and called every provider once to
learn the type of the produced instance.

Commit `5232416` (PR #41) replaced the concrete container annotation with a local `ContainerLike`
protocol. The change was made only to keep BasedPyright's `--verifytypes` result at 100% when
Dependency Injector's own `Container.providers` annotation propagated `Unknown`. It was not made
to support another container implementation. The structural protocol accidentally widened the
runtime contract to arbitrary objects exposing a `providers` mapping, including application-owned
lookalikes.

The eager scan also had correctness and lifecycle consequences:

- factory instances were constructed and discarded during indexing;
- singletons and resources could initialize earlier than their declared lifetime required;
- an unrelated or incompletely configured provider could prevent mediator construction;
- only direct providers were visible, despite `providers.Container` being Dependency Injector's
  documented composition mechanism for modular and decoupled applications;
- `get_all()` resolved every provider again to test `isinstance()`, even when its declared class
  could not match;
- putting the service provider and mediator in their container through `providers.Self()` recursed
  because indexing invoked the mediator provider while the mediator was being built.

The integration needs to preserve PyMediate registration order, provider lifetimes, exact `get()`
semantics, and inheritance-aware `get_all()` semantics while supporting Dependency Injector's
native modular-container pattern.

## Investigation and proposed solutions

### Keep eager, shallow discovery

Continue calling every direct provider and require applications to flatten child containers.

Pros:

- No new constructor argument or inference rules.
- Supports opaque providers because their result is inspected directly.

Cons:

- Retains construction side effects and the `providers.Self()` recursion.
- Makes modular Dependency Injector applications write PyMediate-specific flattening code.
- Resolves unrelated providers during every inheritance-aware lookup.

### Use `container.traverse()`

Dependency Injector documents `traverse()` as a cycle-safe way to visit the complete provider
graph.

Pros:

- Uses an official API and does not construct providers.
- Reaches providers below `providers.Container` boundaries.

Cons:

- Dependency Injector does not guarantee traversal order, while PyMediate behavior order is
  observable.
- Traversal follows all related providers, including dependencies injected into factories. Those
  dependencies are not necessarily declarations intended to be mediator-visible services.
- Filtering the traversal cannot reconstruct the root container's declaration order reliably.

### Ordered recursive declaration scan (recommended)

Walk each container's declared `providers` mapping in order. When a declaration is a
`providers.Container`, recursively walk that child at the declaration's position. Do not follow
ordinary provider dependencies. Guard the active container path to report actual nesting cycles.

Infer types without resolving providers:

- class-backed factories and singleton variants use their declared class;
- `Object`, `List`, and `Dict` have intrinsic runtime types;
- function-backed factories, singletons, and callables use a concrete return annotation;
- composition-only `Configuration`, `Dependency`, `DependenciesContainer`, and `Self` providers
  are skipped unless explicitly declared;
- opaque providers require a `provider_types` entry keyed by the real provider object;
- coroutine providers are rejected because the `ServiceProvider` resolution boundary is
  synchronous for both the sync and async mediators.

Pros:

- Preserves container and behavior declaration order.
- Supports Dependency Injector's modular-container examples without flattening.
- Does not construct or initialize anything while indexing.
- Makes `providers.Self()` mediator composition safe.
- Lets `get_all()` avoid resolving statically incompatible providers.

Cons:

- An unannotated function factory needs one explicit type declaration.
- The indexed type graph is a snapshot; type-changing overrides require rebuilding the service
  provider.
- Runtime-checkable data protocols can still require instance resolution because `issubclass()`
  cannot decide structural instance attributes.

### Require a dedicated service-only container

Require callers to assemble handlers and behaviors in a separate container passed to PyMediate.

Pros:

- Makes the registration boundary completely explicit.
- Avoids indexing unrelated application providers.

Cons:

- Duplicates composition already represented by modular Dependency Injector containers.
- Adds a PyMediate-specific root solely to compensate for the adapter.
- Does not by itself solve eager type discovery or circular construction.

## Decision

Use a concrete `dependency_injector.containers.Container` and ordered recursive declaration scan.

- Treat incomplete Dependency Injector annotations as external in the BasedPyright completeness
  gate with `--ignoreexternal`; do not weaken the public runtime contract to accommodate them.
- Descend only through declared `providers.Container` children and preserve mapping order.
- Never invoke providers to build the index.
- Accept `provider_types: Mapping[providers.Provider[Any], type[Any]]` for opaque providers.
- Support service-provider and mediator providers in the same root container through
  `providers.Self()`.
- Continue delegating actual resolution to the original provider so Factory, Singleton, context
  local, and override behavior remains owned by Dependency Injector.

## Consequences

### Positive

- The public constructor describes the actual integration dependency.
- Nested application containers work without adapters or provider-map lookalikes.
- Factory and resource lifetimes begin at real resolution, not during discovery.
- Circular mediator composition no longer recurses because discovery is static.
- Inheritance-aware resolution constructs only matching services when the relationship is
  statically decidable.

### Negative

- Arbitrary `ContainerLike` objects are no longer accepted.
- Previously invisible providers inside child containers become visible in declaration order.
- Unannotated or dynamically selected service factories need an explicit type.
- A provider override that changes the produced type is not reflected until the service provider
  is rebuilt.

## Migration path

- Replace container lookalikes with a `DeclarativeContainer` or `DynamicContainer`.
- Remove manual flattening used only to expose providers from child containers.
- Add concrete return annotations to function factories, or pass their provider objects in
  `provider_types`.
- Applications may move mediator construction into the root container with `providers.Self()`;
  external construction remains supported.
