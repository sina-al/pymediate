# ADR 0007: Examples as Release Verification

**Status:** Proposed
**Date:** 2026-07-11
**Author:** Claude
**Reviewers:** @sina-al

## Context

The library's own quality gates — the pytest suite, `mypy --strict`, the typing-snippet
corpus, coverage — all run against the **source tree**, inside the repo's own environment,
with the repo's own lockfile. None of them observe what a release actually changes: the
built artifact, its packaging metadata, its resolution from an index into a fresh
environment, and the public API as a downstream project consumes it.

That gap is not hypothetical. The failure modes that live only on the far side of a build
and publish include:

- packaging mistakes: a module missing from the wheel, broken extras, wrong
  `requires-python`, metadata that renders the package uninstallable;
- publish-path mistakes: an index not serving the version, CDN propagation lag (observed
  on v0.3.0 and v0.4.0), Trusted Publishing misconfiguration;
- breaking changes that the library's tests absorb (they're updated in the same commit)
  but downstream code cannot — precisely the changes ZeroVer's minor bump is supposed to
  signal deliberately, not discover accidentally;
- documentation drift: the patterns the docs teach no longer being the patterns that work.

Because PyPI and TestPyPI filenames are immutable forever, any of these discovered *after*
a publish burns the version (see `OPERATIONS.md`, "Burned versions") — and any discovered
by a **user** costs trust that a 0.x library doesn't have to spare. The release pipeline
therefore needs a consumer's view of the package, available before real consumers exist.

## Proposed Solution(s)

### Option A: Smoke imports in the install matrix

Extend `release.yml`'s existing install matrix (3 OS × 3 Pythons, `pip install` the wheel,
import the package) with deeper import checks or a minimal in-line script.

**Pros:**

- Nearly free: infrastructure already exists.
- Catches gross packaging failures (missing modules, broken extras).

**Cons:**

- An import is not usage: dispatch, pipeline behaviors, DI integration, the async mirror —
  none exercised.
- The check code lives inside the repo, drifting toward the repo's perspective rather than
  a consumer's.
- Says nothing about the publish-and-install path from an index.

### Option B: A dedicated post-publish integration-test project

A single hidden test project (e.g. `tests/integration/`) that installs the published
package and runs an API tour.

**Pros:**

- One project to maintain; full API coverage possible.
- Can be as thorough as desired without worrying about readability.

**Cons:**

- Its only reason to exist is the pipeline, so it rots unnoticed between releases and
  nobody proofreads it as *content*.
- Duplicates what the examples gallery already has to be: runnable, tested, downstream-style
  usage of the public API.

### Option C: The examples gallery as proxy downstream users, gating the release at four points (RECOMMENDED)

Make the user-facing examples (`examples/<name>/`) double as the release verification
suite. Each example is a **standalone uv project** that depends on `pymediate` from PyPI
with a loose lower bound, exactly like a real downstream project — and a shared runner
(`scripts/run_examples.py`) re-pins each one to an arbitrary build under test:

- `--wheel PATH` — re-pin to a local wheel via a path source (no index involved);
- `--version X.Y.Z [--index URL]` — re-pin to a published version, resolving *only
  pymediate* from the given index (an `explicit` uv index appended by the runner) while
  every other dependency keeps coming from real PyPI.

The examples contract (`examples/README.md`) is what makes this discovery-based and
zero-wiring: standalone project, committed `uv.lock`, loose `>=` bound so re-pinning never
conflicts, tests runnable by bare `uv sync && uv run pytest`, and no `[tool.uv.sources]`/
`[[tool.uv.index]]` sections (reserved for the runner, which refuses violators). The
runner copies each example to a temp directory, so checkouts are never modified.

Structural consequences, all deliberate:

- **Standalone, not workspace members.** A workspace member resolves pymediate from the
  source tree — the exact thing this system must not test. Standalone projects also open
  clean in an IDE or Codespace, which the gallery needs anyway.
- **Outside the library's lint/type/coverage scopes.** The examples are downstream code;
  holding them to the library's internal tooling would couple them to the repo. Each
  carries its own `[tool.ruff]` and `pyrightconfig.json` instead.
- **Docs and verification are the same artifact.** An example that gates releases cannot
  silently rot, and a verification suite that users read cannot drift into repo-internal
  idioms. Each side keeps the other honest.

The suite then gates the release **four times** — each gate answers a distinct question at
the cheapest point where its failure can be caught:

| # | Where | Mode | Question | Cost of failing here |
|---|---|---|---|---|
| 1 | Release PR (required "Examples" check) | wheel (dev version, built from the cut) | Does this code break downstream users? | none — close the PR |
| 2 | `release.yml`, pre-TestPyPI | wheel (release version, the actual dist artifact) | Does the release artifact, with today's dependency resolution, still work? | none — no version burned yet |
| 3 | `release.yml`, post-TestPyPI | version, TestPyPI index | Does the publish-and-install path work? | version burned |
| 4 | `release.yml`, post-PyPI | version, real PyPI index | Does the exact artifact users install actually work? | release live but unannounced |

Gates 1 and 2 look redundant (same tree) but are not: the examples' dependencies are
re-resolved fresh from PyPI at run time by design — a release PR that sits open lets them
drift between check time and tag time — and gate 1's wheel carries a hatch-vcs dev version
while gate 2 tests the real, release-versioned artifact. Gates 3 and 4 look redundant
(both "install from an index") but are not: PyPI and TestPyPI are separate services with
separate registrations, uploads, and CDNs. Gate 4 **gates the GitHub Release**: the
announcement is created only once the announced artifact is proven installable, extending
the pipeline's "nothing user-visible outlives a failed release" ordering to its last
possible point.

**Pros:**

- The only pre-release signal that sees the package the way users will.
- Every failure class in Context is caught at the cheapest stage that can catch it.
- Zero marginal verification cost per new example — the contract plus discovery means a
  new example is automatically a new release test.
- Documentation quality and release safety reinforce each other.

**Cons:**

- Breaking releases require updating the examples on main *first*, and until that release
  publishes, the updated examples' standalone `uv run pytest` fails against released PyPI —
  a bounded, expected red window (closed by Dependabot's post-release re-lock).
- Examples must stay honest downstream code; the contract has to be enforced mechanically
  (the runner does) or the system degrades into Option B.
- Four CI stages cost minutes per release and two of them can fail on index CDN lag —
  mitigated by probing with uv itself before each index-mode run.

## Decision

Option C. Specifically:

- The examples gallery is the release verification suite; the contract in
  `examples/README.md` is what makes each example machine-runnable against an arbitrary
  build, and `scripts/run_examples.py` is the single runner behind every gate.
- Four gates: release-PR wheel (required check), release wheel (pre-TestPyPI),
  TestPyPI index, PyPI index (smoke test gating the GitHub Release).
- A smoke-test failure at gate 4 withholds the GitHub Release but cannot unpublish;
  the remedy is a maintainer decision (yank and ship the next version, or accept the
  finding and re-run), documented in the `/release` skill.

## Consequences

### Positive

- Releases are verified end to end against the artifact and index users will actually
  hit; the GitHub Release becomes a claim the pipeline has already tested.
- Version numbers stop burning on failures that a pre-publish wheel run can catch.
- Examples can't rot: they run at least four times per release against three different
  distributions of the package.
- Adding an example (via the `example` skill) automatically widens release coverage.

### Negative

- Breaking changes carry a scheduled red window for examples on main between the change
  landing and the release publishing.
- Release wall-clock time grows by the two new stages (a wheel run and a
  CDN-probe-plus-index run), a few minutes each.
- The examples' freshness-by-design (dependencies re-resolved at run time) means a release
  can fail on an upstream package's release — a true signal about what users would hit
  that day, but one the maintainer can't prevent, only respond to.

## Migration Path

No migration needed — this records and completes an existing design: gates 1 and 3
already existed; gates 2 and 4 were added to `release.yml` together with this ADR.

## Open Questions

- Should gate 4's failure eventually page/notify beyond the failed workflow run (e.g. an
  issue auto-filed)? Tentative lean: no — releases are maintainer-attended by design
  (two human approvals), so the failed run is seen.
- Should the examples also run on a schedule (e.g. weekly against latest PyPI) to catch
  upstream dependency breakage between releases? Tentative lean: worth considering if a
  gate-4-style failure ever actually occurs; premature until then.
