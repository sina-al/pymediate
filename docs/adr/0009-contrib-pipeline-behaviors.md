# ADR 0009: A contrib package of in-box pipeline behaviors

**Status:** Rejected
**Date:** 2026-07-12
**Author:** Claude
**Reviewers:** @sina-al

## Context

Issue #13 proposed a `contrib` package of batteries-included, zero-dependency `PipelineBehavior`s —
logging, timing, and retry — shipped with the project so users could register common cross-cutting
behaviors without writing them. This ADR evaluates that proposal and rejects it.

## Decision

**Rejected.** PyMediate will not ship a bundled `contrib` package of in-box behaviors. The simple
zero-dependency behaviors remain documented, copy-paste recipes; any dependency-carrying behaviors
built later ship as separate, narrowly-scoped packages rather than a single umbrella.

## Rationale

**The zero-dependency behaviors are too small to package.** Logging, timing, and retry are each a
handful of lines written against the `PipelineBehavior` contract. Turning them into a package — and
asking a user to take on a dependency to obtain them — is out of proportion to what they contain. A
dependency should earn its keep; a few lines of glue do not. The pipeline-behaviors guide already
carries these as recipes, which is the right weight for them: read the few lines, copy, adjust.

**A batteries collection should be harvested, not invented.** A contrib package earns its place by
proving itself — behaviors that have run in a real production application, accumulated the edge-case
handling that real traffic demands, and shown they are worth reusing unchanged. Curating a bundle
speculatively, ahead of that track record, ships convenience without evidence and commits the
project to maintaining and versioning it regardless.

**The behaviors worth shipping need third-party dependencies.** The genuinely valuable behaviors —
integrations with specific service providers, dependency-injection frameworks, and observability
backends — are precisely the ones that require third-party packages. A *zero-dependency* contrib
excludes exactly the behaviors that would justify its existence, leaving only the trivial ones that
do not.

**A single package would couple unrelated dependencies.** If dependency-carrying behaviors were
bundled into one `contrib` distribution, installing it would pull in dependencies for behaviors the
user will never touch — the dependency of a behavior for one DI framework or service provider
dragged in for someone who only wanted a behavior for a different one. That is the wrong packaging
shape for this class of code.

## Consequences

- No new distribution, no second release lane, and no added public API surface. The library stays
  zero-dependency and small.
- The simple behaviors remain in the pipeline-behaviors guide as roll-your-own recipes.
- **If** dependency-carrying behaviors are built later, each ships as its own fully separate,
  narrowly-scoped package — scoped to a single provider / DI framework / backend and depending only
  on what it needs, never a single umbrella `contrib`. Such a package is created only once a
  specific behavior has proven itself in production, and is scoped by its own ADR/issue at that time.
- The follow-up issue opened for the rejected package's release infrastructure (#63) is closed as
  not planned. Issue #13 stays open as the place to revisit this if a concrete, proven candidate
  appears.

## Note

An unrelated bug in `PipelineBehavior`'s generic type-parameter resolution was found and fixed
separately: a reusable generic behavior (`class Behavior[RequestT](PipelineBehavior[RequestT])`)
either crashed or silently matched every request when scoped by a subclass. That fix is a
self-contained correctness fix and is not contingent on anything in this ADR.
