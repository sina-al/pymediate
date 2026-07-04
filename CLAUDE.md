# CLAUDE.md

Context for agentic work in this repo. Read this before making changes.

## What this is

PyMediate: a type-safe mediator/CQRS-style request-dispatch library for Python 3.12+.
Zero runtime dependencies in core; `dependency-injector` is an optional extra (`di`).
Sync (`pymediate`) and async (`pymediate.aio`) APIs are structural mirrors of each other —
if you change one, check whether the other needs the equivalent change.

## Layout

- `src/pymediate/` — public package. `__init__.py`'s `__all__` is the public API contract.
- `src/pymediate/_internal/` — implementation details, not public API, no back-compat guarantees.
- `src/pymediate/aio/` — async mirror of the sync API.
- `src/pymediate/providers/dependency_injector.py` — optional DI integration (`di` extra).
- `tests/mypy/snippets/{valid,errors}/` — type-level tests, see below. Not ordinary code.
- `docs/adr/` — architecture decision records for nontrivial design changes.
- `scripts/` — standalone maintenance scripts (e.g. `update_uv.py`), invoked via `poe` tasks,
  not part of the package. Still linted/formatted (`poe lint`/`format`/`format:check` cover it).

## Dev workflow — use `poe`, not raw tool invocations

Before running any `poe` task, sync deps with `uv sync --all-extras --group test` (or
`poe install`). Plain `uv sync` only installs the default `dev` group (ruff, mypy, poethepoet) —
pytest and friends live in the separate `test` dependency-group and won't be present without
`--group test`/`--all-groups`, so `poe test` fails with `Failed to spawn: pytest`. `uv.lock` is
gitignored in this repo, so there's no persisted lock to fall back on — every sync re-resolves
against the loose `>=` bounds in `pyproject.toml`, meaning dependency versions (e.g. mypy) can
silently drift between syncs done months apart. See `mypy.ini` history for a concrete case where
a mypy upgrade changed diagnostic output and broke `tests/mypy/test_mypy.py` assertions.

All dev commands go through `poethepoet` (`tasks.toml`) so behavior matches CI exactly:

- `uv run poe test` / `test:fast` / `test:cov` / `test:verbose`
- `uv run poe check` (type + lint + format check) / `check:all` (+ tests with coverage)
- `uv run poe fix` (ruff lint --fix + format)
- `uv run poe dev` — fix + fast tests, the standard inner loop
- `uv run poe pr` — full check before opening a PR
- `uv run poe type` — `mypy src/pymediate/ --strict`

Don't invent bespoke `pytest`/`ruff`/`mypy` invocations — use the `poe` task so local results
match `.github/workflows/*.yml`.

## Quality bar (all enforced in CI, not optional)

- `mypy --strict` on `src/pymediate/` — zero untyped defs in library code. Tests are looser
  (see `mypy.ini` `[mypy-tests.*]`).
- ruff: `E, W, F, I, B, C4, UP`, line length 100, double quotes.
- Coverage floor: 95% (`--cov-fail-under=95` in `release.yml`, checked on PR diff too).
- PR titles must follow Conventional Commits (`feat:`, `fix:`, `docs:`, etc.) — enforced by
  `pr-checks.yml`, will hard-fail otherwise.
- CI flags diffs to `__all__` in `__init__.py`, the `Handler` class, or the resolver protocol
  as potential breaking changes — treat those as places requiring extra care and, likely, an ADR.

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

## Release process

Tag-triggered (`v*.*.*`) via `release.yml`. The workflow hard-fails if the tag version doesn't
match both `pyproject.toml`'s `version` and `src/pymediate/__init__.py`'s `__version__` — bump
both together before tagging. `uv_build` (the build backend) has no dynamic-versioning support,
unlike Hatchling, so this dual bump is a deliberate accepted trade-off, not an oversight.

Before tagging, run `uv run poe changelog` to regenerate `CHANGELOG.md` (via
[git-cliff](https://git-cliff.org/), config in `cliff.toml`) from Conventional Commits, and
commit it alongside the version bump. `release.yml` separately generates the GitHub Release
body for just the new tag's commits — the persisted `CHANGELOG.md` and the per-release notes
are two different git-cliff invocations, not duplicated effort.

Publishing to PyPI (`publish-pypi` job) uses `uv publish` with Trusted Publishing (OIDC) —
no stored credentials. Requires: a `pypi` GitHub environment and a Trusted Publisher
registered on PyPI for this repo/workflow (register a *pending* publisher before the first
release, since the project doesn't exist on PyPI until then).

## Docs

MkDocs + Material, deployed to GitHub Pages from `main` via `docs.yml`. Structure under `docs/`
mirrors `getting-started/ → guide/ → advanced/ → api/ → examples/ → adr/`. Built with `--strict`
(warnings fail the build), so keep internal links and mkdocstrings refs valid when moving code.
