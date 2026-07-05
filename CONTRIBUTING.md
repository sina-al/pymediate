# Contributing to PyMediate

Thanks for considering a contribution. This is a small, solo-maintained library, so keep
proposals in scope with a quick issue first if you're planning something larger than a
bug fix.

## Setup

```bash
git clone https://github.com/sina-al/pymediate.git
cd pymediate
uv sync --all-extras --group test
```

`uv sync` alone only installs the default `dev` group (ruff, mypy, poethepoet) — the
`--group test` above is required to get pytest and friends. See [`README.md`](README.md)
for the full command list.

## Workflow

All dev commands go through [Poe the Poet](https://poethepoet.natn.io/) (`tasks.toml`), so
local results match CI exactly. Don't invent bespoke `pytest`/`ruff`/`mypy` invocations.

```bash
uv run poe dev       # fix formatting/lint + fast test run — the standard inner loop
uv run poe pr        # full check before opening a PR (fix, strict mypy, lint, tests+coverage)
```

Run `uv run poe` with no arguments to see every available task.

## Before opening a PR

- **Tests**: new behavior needs test coverage. The CI-enforced floor is 95% (`poe test:release`
  is the exact gate a release runs).
- **Types**: `src/pymediate/` is checked with `mypy --strict` — zero untyped defs.
- **PR title**: must follow [Conventional Commits](https://www.conventionalcommits.org/)
  (`feat:`, `fix:`, `docs:`, `chore:`, etc.) — this is enforced by CI and also feeds the
  auto-generated changelog.
- **Public API changes**: diffs to `__all__` in `src/pymediate/__init__.py`, the `Handler`
  class, or the `ServiceProvider` protocol are treated as potential breaking changes.
  Nontrivial design or API changes should include an ADR in `docs/adr/` (see existing
  ones for the template).
- **Docstrings**: `src/pymediate/` docstrings (outside `_internal/`) are rendered into the
  public API docs — see [`CLAUDE.md`](CLAUDE.md#docstrings) for what belongs in them (and
  what doesn't), which sections actually render, and why every example needs to be verified
  to run, not just look plausible.

## The mypy-snippet tests

`tests/mypy/snippets/errors/*.py` are **deliberately type-invalid** — `tests/mypy/test_mypy.py`
asserts mypy fails on every file there. If you see a mypy error under `errors/`, that's the
test working correctly. Never add `# type: ignore` or an exclusion for those files.

## Questions

Open an issue — happy to discuss design direction before you invest time in a larger change.
