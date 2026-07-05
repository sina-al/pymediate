# CLAUDE.md

Context for agentic work in this repo. Read this before making changes.

## What this is

PyMediate: a type-safe mediator/CQRS-style request-dispatch library for Python 3.12+.
Zero runtime dependencies in core; `dependency-injector` is an optional extra (`di`).
Sync (`pymediate`) and async (`pymediate.aio`) APIs are structural mirrors of each other —
if you change one, check whether the other needs the equivalent change.

## Layout

- `src/pymediate/` — public package. `__init__.py`'s `__all__` is the public API contract.
  - `_internal/` — implementation details, not public API, no back-compat guarantees.
  - `aio/` — async mirror of the sync API.
  - `providers/dependency_injector.py` — optional DI integration (`di` extra).
- `tests/` — pytest suite, roughly one `test_*.py` per `src/pymediate/` module (e.g.
  `test_handler.py`, `test_mediator.py`); `conftest.py` holds shared fixtures.
  - `tests/mypy/snippets/{valid,errors}/` — type-level tests, see "The mypy-snippet test
    system" below. Not ordinary code.
- `docs/` — MkDocs source; see "Docs" below.
  - `docs/adr/` — architecture decision records for nontrivial design changes; see "ADRs" below.
- `scripts/` — standalone maintenance scripts (e.g. `update_uv.py`), invoked via `poe` tasks,
  not part of the package. Still linted/formatted (`poe lint`/`format`/`format:check` cover it).
- `assets/` — static files referenced elsewhere (currently just `logo.svg`, used in
  `README.md`); not part of the package, not built or published.
- `.github/workflows/` — CI pipelines; see "GitHub Actions workflows" below.
- `.claude/` — Claude Code config for this repo: `settings.json`, project-specific skills
  (`adr`, `release`, `update-uv`), and `.claude/context/*.md` — generated files imported into
  this CLAUDE.md (see "API Signatures" and "ADRs" below); regenerate, don't hand-edit.

## Dev workflow — use `poe`, not raw tool invocations

Before running any `poe` task, sync deps with `uv sync --all-extras --group test` (or
`poe install`). Plain `uv sync` only installs the default `dev` group (ruff, mypy, poethepoet) —
pytest and friends live in the separate `test` dependency-group and won't be present without
`--group test`/`--all-groups`, so `poe test` fails with `Failed to spawn: pytest`. `uv.lock` is
committed to the repo, so `uv sync` resolves against pinned versions, not the loose `>=` bounds
in `pyproject.toml` — run `uv lock --upgrade` (or `--upgrade-package <name>`) deliberately when you
want to bump a dependency, and commit the updated lockfile. See `mypy.ini` history for a concrete
case, before the lockfile was committed, where an unpinned mypy upgrade changed diagnostic output
and broke `tests/mypy/test_mypy.py` assertions.

All dev commands go through `poethepoet` (`tasks.toml`) so behavior matches CI exactly:

- `uv run poe test` / `test:fast` / `test:cov` / `test:verbose`
- `uv run poe check` (type + lint + format check) / `check:all` (+ tests with coverage)
- `uv run poe fix` (ruff lint --fix + format)
- `uv run poe dev` — fix + fast tests, the standard inner loop
- `uv run poe pr` — full check before opening a PR
- `uv run poe type` — `mypy src/pymediate/ --strict`

Don't invent bespoke `pytest`/`ruff`/`mypy` invocations — use the `poe` task so local results
match `.github/workflows/*.yml`.

## GitHub Actions workflows

Before adding a new file under `.github/workflows/**` or editing an existing one, apply the
`github-actions-security` skill (action pinning, least-privilege `permissions:`, script-injection
prevention, OIDC over long-lived secrets, safe trigger scoping). This applies any time the task
touches a workflow file, not only when security is mentioned explicitly.

## Quality bar (all enforced in CI, not optional)

- `mypy --strict` on `src/pymediate/` — zero untyped defs in library code. Tests are looser
  (see `mypy.ini` `[mypy-tests.*]`).
- ruff: `E, W, F, I, B, C4, UP, D`, line length 100, double quotes. `D` (pydocstyle, Google
  convention) is scoped to `src/pymediate/` excluding `_internal/` — see "Docstrings" below.
- Coverage floor: 95% (`--cov-fail-under=95` in `release.yml`, checked on PR diff too).
- PR titles must follow Conventional Commits (`feat:`, `fix:`, `docs:`, etc.) — enforced by
  `pr.yml`, will hard-fail otherwise.
- CI flags diffs to `__all__` in `__init__.py`, the `Handler` class, or the `ServiceProvider`
  protocol as potential breaking changes — treat those as places requiring extra care and,
  likely, an ADR. These are also the surfaces "Versioning" below uses to decide minor vs. patch.

## Docstrings

Docstrings in `src/pymediate/` (except `_internal/`) are rendered into the public API docs via
mkdocstrings (`docs/api/*.md`, `docstring_style: google` in `mkdocs.yml`) — write them for that
reader, not for someone reading the source in an editor.

- **No internal implementation rationale.** Design tradeoffs ("why a dict and a list," "why not
  weak references," historical two-parameter designs) belong in an ADR or a commit message, not
  a docstring — they don't help someone calling the API, and they rot silently once the
  implementation moves on. This bit us once: `service.py`'s module docstring carried a 40-line
  "Architecture Notes" section that a docs audit had to strip out.
- **No private attributes.** Don't document `_leading_underscore` attributes in a class
  docstring's `Attributes:` section — they're not part of the contract, and mkdocstrings'
  `filters: ["!^_"]` won't render them anyway.
- **Stick to sections griffe's Google parser actually recognizes**: `Args`, `Returns`, `Raises`,
  `Yields`, `Attributes`, `Examples` (plural), `Note`, `Warning`, `Type Parameters`. Anything
  else (`Thread Safety:`, `Performance:`, `See Also:`, `Use Cases:`, ...) still renders — griffe
  falls back to a generic admonition box for unrecognized headers — but repeating one on every
  method produces a wall of low-value callout boxes rather than useful docs. Prefer folding a
  real constraint into prose or a single `Note:`, and use `See Also:` sparingly.
- **Every code example must actually run.** Verify it in a scratch shell before committing it,
  the same way you'd verify one in `docs/`. This project has shipped broken examples before -
  missing `@dataclass` decorators, an undefined `resolver` variable, a `providers.Self()`
  self-registration pattern that recurses infinitely - all inside docstrings, none caught until
  someone ran them.
- Sync (`pymediate`) and async (`pymediate.aio`) docstrings are structural mirrors, same as the
  code — if you fix or reword one, check the other side for the identical issue.
- `poe lint` enforces docstring presence/formatting (ruff's `D` rules, Google convention) on
  `src/pymediate/` excluding `_internal/`; it won't catch stale content or broken examples, so
  don't rely on it as the only check.

## The mypy-snippet test system — do not "fix" these

`tests/mypy/snippets/errors/*.py` are **deliberately type-invalid**. `tests/mypy/test_mypy.py`
asserts mypy fails on every file in `errors/` and passes on every file in `valid/`. If you see
a mypy error in `errors/`, that's the test working correctly — never add `# type: ignore`,
never add them to `mypy.ini` exclusions, never "correct" the type error. Only touch these files
if you're intentionally adding/removing a type-safety test case, and if so, extend the
corresponding assertion in `test_mypy.py`.

## ADRs

Nontrivial design/API changes get a numbered ADR in `docs/adr/`, following the existing
template (Context → Investigation/Proposed Solutions → Pros/Cons → Decision → Consequences).
Existing ADRs (0001, 0002) were authored by Claude and reviewed by @sina-al (repo owner's GitHub
handle) — continue that pattern for anything touching public API shape, generics design, or
breaking changes. Use the `/adr` skill to scaffold a new one.

@.claude/context/adr-index.md

Generated from `docs/adr/*.md` by `uv run poe context:update` (`scripts/update_context.py`); run
`uv run poe context:check` to confirm it isn't stale. Don't hand-edit that file. Note ADR 0002
revisits and overturns part of ADR 0001's decision — read both before assuming either alone is
current.

## Versioning

PyMediate follows [ZeroVer](https://0ver.org/): the major version stays at `0` indefinitely —
there's no planned 1.0. This is consistent with, not a workaround of, SemVer itself: SemVer's
own clause 4 says "Major version zero (0.y.z) is for initial development. Anything MAY change
at any time. The public API SHOULD NOT be considered stable."

Since major can never carry a signal, minor and patch split that job between them:

- **Minor** (`0.X.0`) — a breaking change to the public API, or a new backward-compatible
  feature. "Breaking" here means the same surfaces already called out in "Quality bar" below:
  a removed/changed name in `__init__.py`'s `__all__`, or a removed/changed public symbol in
  `Handler` or the `ServiceProvider` protocol.
- **Patch** (`0.1.X`) — bug fixes, docs, refactors, tooling — anything with no public API impact.

`scripts/release_impact.py` (via `poe release:impact`) automates this assessment by diffing
commits and the flagged API surface since the last tag, and the `/release` skill runs it and
asks you to confirm the recommendation before bumping.

## Release process

Use the `/release` skill for the full step-by-step checklist. Summary below.

Tag-triggered (`v*.*.*`) via `release.yml`. The workflow hard-fails if the tag version doesn't
match both `pyproject.toml`'s `version` and `src/pymediate/__init__.py`'s `__version__`. Bump
both together with `uv run poe version:bump patch|minor` (or an explicit `X.Y.Z` — see
"Versioning" above for why `major` isn't part of the normal flow) —
it wraps `uv version` (which only touches `pyproject.toml`; `uv_build` has no dynamic-versioning
support unlike Hatchling) and syncs `__init__.py` to match. Add `--dry-run` to preview.

Before tagging, run `uv run poe changelog` to regenerate `CHANGELOG.md` (via
[git-cliff](https://git-cliff.org/), config in `cliff.toml`) from Conventional Commits, and
commit it alongside the version bump. `release.yml` separately generates the GitHub Release
body for just the new tag's commits — the persisted `CHANGELOG.md` and the per-release notes
are two different git-cliff invocations, not duplicated effort.

Publishing uses `uv publish` with Trusted Publishing (OIDC) — no stored credentials — staged
through TestPyPI first (`publish-testpypi` job) and gating the real `publish-pypi` job on that
succeeding. Requires: `pypi` and `testpypi` GitHub environments (already created) and a Trusted
Publisher registered on **both** pypi.org and test.pypi.org for this repo/workflow — they're
separate services with separate registrations. Register a *pending* publisher on each before
the first release, since the project doesn't exist on either index yet.

## Docs

MkDocs + Material, deployed to GitHub Pages from `main` via `docs.yml`. Structure under `docs/`
mirrors `getting-started/ → guide/ → advanced/ → api/ → examples/ → adr/`. Built with `--strict`
(warnings fail the build), so keep internal links and mkdocstrings refs valid when moving code.

## API Signatures

@.claude/context/api-signatures.md

Generated from source by `uv run poe context:update` (`scripts/update_context.py`); run
`uv run poe context:check` to confirm it isn't stale. Don't hand-edit that file.
