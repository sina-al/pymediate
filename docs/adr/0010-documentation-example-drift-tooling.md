# ADR 0010: Documentation Example Drift Tooling

**Status:** Proposed
**Date:** 2026-07-12
**Author:** Claude
**Reviewers:** @sina-al

## Context

PyMediate teaches itself almost entirely through code. Across three surfaces there are
roughly **235 runnable-looking Python snippets**, and **none of them are executed against
the real API**:

- **Docstrings** (`src/pymediate/**`, excluding `_internal/`) — ~18 files carry Google-style
  `Examples:` blocks with fenced ` ```python ` code. There is not a single `>>>` doctest
  prompt in the tree, so nothing runs them.
- **Docs site** (`docs/content/**`) — ~231 ` ```python ` blocks across 34 `.mdx` files.
  `docs.yml` runs `pnpm check` (ESLint + `fumadocs-mdx` + `tsc --noEmit`) and `pnpm build`;
  it never touches the Python.
- **README** (`README.md`) — 4 quick-start blocks (async, its sync mirror, a pipeline
  behavior), unverified.

This is a real, recurring failure mode, not a hypothetical. The `CLAUDE.md` docstring policy
already records that this project *has shipped broken examples* — a missing `@dataclass`
decorator, an undefined `resolver`, a `providers.Self()` pattern that recurses infinitely —
each caught only when a human eventually ran it. Every one of those was a public-facing snippet
that looked plausible and did not work.

The exposure is sharpened by two repo-specific facts:

- **The async/sync mirror doubles every example.** Guidance in `pymediate` (async) is mirrored
  in `pymediate.sync`, so a drift fix on one side usually has a twin on the other — twice the
  surface, twice the chance one half rots while the other is updated.
- **The snippets are deliberately fragments, not programs.** For IDE-hover and page readability
  they reference names defined elsewhere — `AsyncCreateUserHandler`, `UserCreatedResponse`,
  `CreateUserRequest` — rather than redefining a full cast in every block. This is a feature of
  the docs, and it is the single most important constraint on tool choice: any tool that
  requires each block to be a self-contained, importable program turns adoption into a
  rewrite-hundreds-of-examples project.

It helps to separate "drift" into three distinct problems, because no single tool covers all
three and they demand different mechanisms:

- **D1 — Example execution drift.** A snippet still parses and looks right but no longer runs:
  a renamed method, a changed constructor, a dropped import. This is the large, unprotected
  exposure above.
- **D2 — Signature/description drift.** A docstring's `Args:`/`Returns:`/`Raises:` — or the
  hand-written API-reference MDX that mirrors it (`docs/content/docs/api/*.mdx`) — describes a
  parameter that no longer exists, or omits a new one. Prose, not runnable code.
- **D3 — Single-source vs. mirror.** The API-reference pages hand-mirror docstrings, and
  `examples/` plus the typing-snippet corpus are rigorously tested but are **not derived from**
  the prose docs. Nothing links the tested artifacts to the taught ones.

What the repo already owns is worth stating, because the decision builds on it rather than
replacing it:

- **`tests/typing/snippets/`** — 37 snippets run under `mypy --strict`, basedpyright (standard
  and recommended), *and executed at runtime* (`test_snippets_runtime.py`). Genuine
  example-testing — but a bespoke typing corpus, authored separately from the docs.
- **`examples/`** — 7 standalone uv projects, each with its own pytest suite, run against the
  built wheel / PyPI by `scripts/run_examples.py` (ADR 0007). Catches packaging and install
  drift; not the docstring/`.mdx`/README snippets.
- **griffe** — `poe context:check` regenerates `api-signatures.md` from source and fails if
  stale; `poe api:check` runs `griffe check` for public-API breaking changes. Partial cover for
  D2/D3 at the signature level, nothing for D1.

So the tested surfaces are strong and the taught surfaces are unguarded, with no bridge between
them. The question this ADR settles is whether ~235 unverified public snippets is an acceptable
standing risk, and if not, what to adopt given the fragment constraint and the Fumadocs stack.

## Proposed Solution(s)

### Option A: Keep as-is

Record a deliberate no-adoption decision. The rationale is not empty: the load-bearing
examples are effectively covered elsewhere (`examples/` and the typing corpus), the library is
ZeroVer and low-churn, and a broken snippet is cheap to fix reactively when a user reports it.

**Pros:**

- Zero new tooling, zero new dependency, zero CI time.
- No risk of a flaky doc-test job gating an otherwise-green PR.

**Cons:**

- Leaves the largest body of public-facing code — the first thing a new user copies —
  structurally unverified, exactly where the project has been burned before.
- "Fix reactively when a user reports it" spends trust a 0.x library doesn't have to spare,
  and pushes discovery onto the far side of the docs where it costs the most.
- The async/sync mirror means silent half-drift (one side fixed, the twin missed) is a
  standing likelihood, not an edge case.

### Option B: `pytest-markdown-docs` (RECOMMENDED for D1)

A pytest plugin (modal-labs, MIT) that discovers ` ```python ` fences in markdown **and**
docstrings and runs them as tests (`pytest --markdown-docs`).

**Pros:**

- The only mainstream runner that names `.mdx` as a first-class target — directly matches the
  docs stack — and it also covers docstrings and the README in the same pass.
- The `pytest_markdown_docs_globals()` conftest hook injects a shared namespace (the recurring
  handler/request cast) into every block, so the fragment snippets run **without being
  rewritten**. `continuation` blocks share state across a page; `notest` exempts genuinely
  illustrative-only blocks.
- Async works via `pytest-asyncio`, which the async mirror needs.

**Cons:**

- No expected-output matching — assertion-based only. Acceptable for a library (examples
  demonstrate wiring, not REPL output), less so for tutorial output.
- Traceback line numbers can be off, especially inside docstrings; the author acknowledges
  parts of the internals are "hacky."
- Smaller project than Sybil — a thinner bus factor to weigh.

### Option C: `sybil`

The most mature option (simplistix, 10.x): parsers for reST, CommonMark/GFM/MyST, and Python
docstrings, with examples evaluated in a shared per-document namespace and first-class
`skip`/`clear-namespace` directives.

**Pros:**

- Richest and best-documented; the shared-namespace model fits guide pages that build a
  scenario across several blocks; strong maintenance and adoption.

**Cons:**

- Heaviest to configure (assemble parsers/evaluators in a docs `conftest.py`; async needs an
  async-capable evaluator wired explicitly).
- No native `.mdx` awareness — you point a markdown parser at the files, and MDX-specific JSX
  (`<Tabs>`, `<include>`) can trip a strict CommonMark/MyST parser. That risk lands squarely on
  our most example-dense surface.

### Option D: `pytest-examples`

Pydantic's plugin: runs examples, lints them with ruff/black, and can auto-format and inline
expected `#>` output via `--update-examples`.

**Pros:**

- Format + lint + output-checking as first-class, matching the repo's strict-quality culture;
  battle-tested inside Pydantic.

**Cons:**

- Its model is one self-contained example per block — no shared-namespace/continuation story,
  so our undefined-name fragments would each have to become whole programs. That is precisely
  the rewrite the fragment constraint rules out.
- `.md`-focused; `.mdx` is not a declared target. Still 0.0.x.

### Option E: Fumadocs `<include>` single-sourcing (for D3)

Fumadocs natively renders `<include>./snippet.py</include>` — a real `.py` file — as a
syntax-highlighted code block, with region markers for partial includes.

**Pros:**

- Eliminates drift **by construction** for the docs site: the shown code *is* a file that our
  existing `examples/` / typing machinery can run and type-check. No new Python dependency —
  it is already in the Fumadocs stack.

**Cons:**

- Docs-site only — does nothing for docstrings or the README.
- Migration cost: authored-inline blocks become file references, changing the docs authoring
  workflow; whole-file/region granularity makes very small inline fragments awkward.

### Option F: `pydoclint` (for D2)

A fast, AST-based docstring linter (jsh9) that checks whether Google-style
`Args`/`Returns`/`Raises` sections match the actual function signature, with a `baseline`
feature for incremental adoption.

**Pros:**

- Directly targets the drift execution can never catch: a stale `Args:` line that still parses
  and runs. Cheap, fast, ruff-adjacent, and it protects exactly the docstrings the API-reference
  MDX mirrors.

**Cons:**

- Doesn't run examples and doesn't see the MDX; it validates docstring↔signature, not
  docstring↔MDX. Adds a second docstring linter next to ruff's `D` rules (non-redundant on the
  signature check, but conceptually overlapping).

### Also considered, dismissed

- **`doctest` / `pytest --doctest-*`** — our examples are fenced fragments, not `>>>` REPL
  sessions with expected output. Adopting means rewriting everything into doctest form and
  maintaining brittle output strings; async needs wrapping. Zero-dependency is its only draw.
- **`mktestdocs`** — pleasantly minimal, but you hand-write the parametrization and it lacks the
  globals-injection ergonomics the fragments need. A fine fallback if the smallest possible
  dependency is the priority.
- **`phmdoctest`** — oriented around code+expected-output blocks with HTML-comment directives;
  more ceremony than value for a fragment-heavy `.mdx` corpus.
- **`doccmd`** — tempting because it can run `mypy --strict` against doc blocks (matching our
  type bar), but the fragment problem bites *harder* under a type-checker (an undefined name is
  a hard error), and `.mdx` isn't a declared target. Kept in reserve as a possible README-only
  complement.
- **`cog`** — a code *generator*, not an example runner; overlaps what `update_context.py`
  already does with griffe. Only relevant for generating API tables into MDX (D3), where griffe
  is the better-owned path.

## Decision

Adopt a **layered** approach rather than a single tool, because the three drift dimensions are
genuinely distinct and the cheapest cover for each comes from a different place. Keep-as-is
(Option A) is rejected: the exposure is the project's own documented failure mode, on its
highest-traffic surface.

- **Layer 1 — `pytest-markdown-docs` for D1 (primary).** Execute the `.mdx`, README, and
  docstring snippets. Seed `pytest_markdown_docs_globals()` with the recurring handler/request
  cast so fragments run unmodified; mark genuinely illustrative-only blocks `notest`; use
  `pytest-asyncio` for the async side. This retires the bulk of the execution exposure without
  rewriting examples.
- **Layer 2 — `pydoclint` for D2 (complement).** Add signature↔docstring parity checking to the
  lint lane, adopting via `baseline` so it doesn't block on the existing corpus.
- **Layer 3 — Fumadocs `<include>` for D3 (phased, optional).** For the load-bearing quick-start
  and core-guide examples, replace inline blocks with includes of files the `examples/` / typing
  machinery already runs. Surgical, not a blanket migration.

Binding process constraints on the implementation (not decided here — see the tracking issue):

- **Everything runs through `poe` and CI.** Per `CLAUDE.md`, `tasks.toml` is the single source
  of truth for any command a human or agent also runs locally; the doc-test invocation must be a
  poe task, and the CI job must call that task, not a bespoke `pytest --markdown-docs` line.
  Because `docs.yml` is a Node-only job (the "poe tasks vs. inline workflow steps" carve-out),
  the Python doc-test job belongs in `test.yml` (or a new Python job), **not** in `docs.yml`.
- **Core stays zero-runtime-dependency.** These are test/dev tools — they enter a
  dependency-group (like `test`), never the package's runtime requirements.
- **Both mirror sides are in scope.** Async and sync snippets are structural mirrors; the runner
  and its shared globals must cover both.

## Consequences

### Positive

- The largest body of public-facing code stops being structurally unverified; a renamed method
  or dropped import in `src/` fails a doc-test the same commit it lands, before a user copies it.
- The async/sync mirror is held honest on both sides at once, closing the silent-half-drift gap.
- D2 gains real cover (`pydoclint`) that execution testing fundamentally cannot provide.
- Layer 3 turns the docs↔tests relationship from "mirror by discipline" into "single source by
  construction" for the examples that matter most.
- Each layer is independently landable and independently valuable — Layer 1 alone justifies the
  change; Layers 2 and 3 can follow without blocking it.

### Negative

- A shared-globals `conftest.py` becomes a maintained artifact: the recurring cast has to be kept
  in step with the API, and `notest` markers need curating so the exemption list doesn't quietly
  grow into "most blocks skipped."
- `pytest-markdown-docs`' traceback line-number quirks make some failures marginally harder to
  locate, especially in docstrings.
- A new CI job adds wall-clock time and a new class of red PR (a doc snippet that no longer runs)
  — which is the point, but it does raise the bar for docs changes.
- Two docstring linters (ruff `D` + `pydoclint`) coexist; contributors must understand they check
  different things.
- `<include>` migration (Layer 3) changes how docs authors write those pages.

## Migration Path

No migration needed for this ADR — it records a decision. The implementation (dependency-group
entries, `conftest.py` globals hook, `poe` task, CI job, `pydoclint` baseline, and the phased
`<include>` follow-up) is tracked in [sina-al/pymediate#72](https://github.com/sina-al/pymediate/issues/72),
filed alongside this ADR, so the "why" (here) and the "do" (the issue) stay separate. This work is **patch**-level under ZeroVer:
it touches no public API surface (`__all__`, `RequestHandler`, `ServiceProvider`).

## Open Questions

- Should doc snippets eventually be **type-checked** as well as run (e.g. `doccmd` with
  `mypy --strict`, or a basedpyright pass), to hold them to the same bar as `src/` and the typing
  corpus? Tentative lean: valuable but secondary — get execution coverage first; revisit once the
  shared-globals `conftest.py` exists, since a type-checker would reuse it.
- Should the README be enforced through the same job or a separate lane, given it lives outside
  `docs/`? Tentative lean: same job, globbed in — one doc-test task over all three surfaces.
- Where should Layer 1's shared example cast live so it doesn't itself drift — a fixtures module
  imported by both the globals hook and the typing snippets? Tentative lean: yes, single-source
  the cast too; defer the exact shape to implementation.
