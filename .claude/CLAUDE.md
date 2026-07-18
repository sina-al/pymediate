# CLAUDE.md

Context for agentic work in this repo. Read this before making changes.

## What this is

PyMediate: a type-safe mediator/CQRS-style request-dispatch library for Python 3.12+.
Zero runtime dependencies in core; `dependency-injector` is an optional extra (`di`).
Async (the top-level `pymediate`) and sync (`pymediate.sync`) APIs are structural mirrors of
each other — if you change one, check whether the other needs the equivalent change. A parity
test (`tests/test_parity.py`) enforces that every shared name is the identical object in both
namespaces, with `RequestHandler`/`EventHandler`/`Mediator`/`PipelineBehavior` as the only
intentional variants (ADR 0008).

## Layout

- `src/pymediate/` — public package. `__init__.py`'s `__all__` is the public API contract.
  - `_internal/` — implementation details, not public API, no back-compat guarantees.
  - `sync/` — sync mirror of the async top-level API.
  - `providers/dependency_injector.py` — optional DI integration (`di` extra).
- `tests/` — pytest suite, roughly one `test_*.py` per `src/pymediate/` module (e.g.
  `test_handler.py`, `test_mediator.py`); `conftest.py` holds shared fixtures.
  - `tests/typing/snippets/{valid,errors}/` — type-level tests, see "The typing-snippet test
    system" below. Not ordinary code.
- `docs/` — the documentation site, a Next.js + Fumadocs app (pnpm, static export); see
  "Docs" below. Site content lives in `docs/content/`; the rest is app code.
  - `docs/adr/` — architecture decision records for nontrivial design changes; see "ADRs"
    below. Deliberately outside `docs/content/`, so they are never published on the site.
- `examples/` — standalone uv projects demonstrating the package against its *released*
  PyPI distribution (not the source tree); each satisfies the contract in
  `examples/README.md`, and the release pipeline runs them all four times via
  `scripts/run_examples.py` (release-PR wheel, release wheel, TestPyPI, PyPI smoke —
  see OPERATIONS.md and ADR 0007). Not covered by the library's lint/type/coverage
  scopes — each example carries its own `[tool.ruff]`, `pyrightconfig.json`, and
  `.vscode/settings.json` so it's pleasant opened standalone. **Any work on an example
  (new, restructure, or README edit) goes through the `example` skill** — it owns the
  structure rules, README template, IDE-polish checklist, per-example devcontainers
  (`.devcontainer/<example>/`, Codespaces badges), and the verification bar.
- `scripts/` — standalone maintenance scripts (e.g. `update_uv.py`), invoked via `poe` tasks,
  not part of the package. Still linted/formatted (`poe lint`/`format`/`format:check` cover it).
- `OPERATIONS.md` — the reference for how code gets in (contribution lanes) and releases
  get out (two-branch model, rulesets, identities). Read it before touching anything
  release- or ruleset-related.
- `assets/` — static files referenced elsewhere (currently just `logo.svg`, used in
  `README.md`); not part of the package, not built or published.
- `.github/workflows/` — CI pipelines; see "GitHub Actions workflows" below.
- `.claude/` — Claude Code config for this repo: `settings.json`, project-specific skills
  (`adr`, `release`, `update-uv`, `compare`, `example`, `edict`), and `.claude/context/*.md`:
  `api-signatures.md` is generated and imported into this CLAUDE.md (see "API Signatures"
  below) — regenerate, don't hand-edit; `mediator-survey.md` is the `/compare` skill's
  anonymized competitor knowledge base backing the docs site's comparison page — updated by
  that skill, and it must never contain library names or other identifying details.

## Dev workflow — use `poe`, not raw tool invocations

Before running any `poe` task, sync deps with `uv sync --all-extras --group test` (or
`poe install`). Plain `uv sync` only installs the default `dev` group (ruff, mypy, poethepoet) —
pytest and friends live in the separate `test` dependency-group and won't be present without
`--group test`/`--all-groups`, so `poe test` fails with `Failed to spawn: pytest`. `uv.lock` is
committed to the repo, so `uv sync` resolves against pinned versions, not the loose `>=` bounds
in `pyproject.toml` — run `uv lock --upgrade` (or `--upgrade-package <name>`) deliberately when you
want to bump a dependency, and commit the updated lockfile. See `mypy.ini` history for a concrete
case, before the lockfile was committed, where an unpinned mypy upgrade changed diagnostic output
and broke `tests/typing/test_mypy.py` assertions.

All dev commands go through `poethepoet` (`tasks.toml`) so behavior matches CI exactly:

- `uv run poe test` / `test:fast` / `test:cov` / `test:verbose`
- `uv run poe check` (type + lint + format check) / `check:all` (+ tests with coverage)
- `uv run poe fix` (ruff lint --fix + format)
- `uv run poe dev` — fix + fast tests, the standard inner loop
- `uv run poe pr` — full check before opening a PR
- `uv run poe type` — `mypy src/pymediate/ --strict`

Don't invent bespoke `pytest`/`ruff`/`mypy` invocations — use the `poe` task so local results
match `.github/workflows/*.yml`.

Optional commit-time gate: `uvx pre-commit install` (once per clone) wires
`.pre-commit-config.yaml` — format check, lint, and api-signatures freshness at every
commit, running the same poe tasks as CI. Local hooks only, so tool versions come from
`uv.lock` rather than a second pin.

## GitHub Actions workflows

zizmor owns the security bar for `.github/workflows/**` — run `uv run poe actions:lint`
after any edit; `checks.yml` enforces it in CI, so a finding you don't fix or explicitly
ignore (with a justification comment) will fail the PR. Its audits mechanically cover
action pinning, template injection, permissions, dangerous triggers, and trusted
publishing. The judgment calls it can't lint — trigger scoping (`paths:`/`branches:` +
concurrency), `workflow_run` privilege separation over `pull_request_target`, whether a
new third-party action is warranted at all — are injected at edit time by
`.claude/hooks/pre_edit_reminders.py`.

### poe tasks vs. inline workflow steps

`tasks.toml` is the single source of truth for any command a human or agent might also run
locally — that's what keeps local results matching CI. When writing a workflow `run:` step,
decide where the command lives:

**Poe task, when all of these hold:**

- it runs the project toolchain (pytest, ruff, mypy, uv build, twine, `scripts/*.py`, ...)
  needing nothing beyond `uv sync` and the repo;
- it's meaningful to run locally, and running the *identical* invocation there matters;
- the invocation is stable across call sites — passing runtime values (a version, an index
  URL, a git ref) as task arguments is fine, but the flag *shape* shouldn't depend on CI
  event context.

**Inline in the workflow, when any of these hold:**

- it needs CI context: `github.*` values, `GITHUB_OUTPUT`/`GITHUB_ENV`, `needs.*.result`,
  tokens, OIDC;
- it needs tools outside the uv-managed environment: `gh`, `git push`, pnpm/Node, or
  pip-as-an-end-user (release.yml's install matrix deliberately avoids uv);
- it *is* the bootstrap (`uv sync` — poe isn't installed yet);
- it's single-call-site CI glue: summary gates over job results, path filters, ref guards.

Carve-out: jobs whose toolchain isn't Python (docs.yml's Node-only build) don't bootstrap
uv/poe just for parity — they run their tools directly, and the workflow steps and the
mirroring poe tasks must cross-reference each other in comments so drift is caught in review.

A raw invocation in a workflow that an existing poe task already wraps is a bug — route it
through the task. This regressed once and propagated: release.yml's `run_examples.py` call
predated both the runner and the `examples:test` task (it was a placeholder for issue #24),
the task landed later without retrofitting the workflow, and three subsequent examples jobs
copied the workflow's raw pattern instead of the task. Copying an adjacent step is how
conventions erode — check `tasks.toml` first, not the neighboring job.

## Quality bar (all enforced in CI, not optional)

- `mypy --strict` on `src/pymediate/` — zero untyped defs in library code. Tests are looser
  (see `mypy.ini` `[mypy-tests.*]`).
- ruff: `E, W, F, I, B, C4, UP, D`, line length 100, double quotes. `D` (pydocstyle, Google
  convention) is scoped to `src/pymediate/` excluding `_internal/` — see "Docstrings" below.
- Coverage floor: 95% (`--cov-fail-under=95` in `release.yml`, checked on PR diff too).
- PR titles must follow Conventional Commits (`feat:`, `fix:`, `docs:`, etc.) — enforced by
  `pr.yml`, will hard-fail otherwise.
- CI flags diffs to `__all__` in `__init__.py`, the `RequestHandler` class, or the `ServiceProvider`
  protocol as potential breaking changes — treat those as places requiring extra care and,
  likely, an ADR. These are also the surfaces "Versioning" below uses to decide minor vs. patch.

## Docstrings

Docstrings in `src/pymediate/` (except `_internal/`) are public-facing: they reach users
through IDE hover/`help()`, and the hand-written API reference pages
(`docs/content/docs/api/*.mdx`) mirror them — when you change a public docstring or
signature, check whether the matching API page needs the same change. Write docstrings for
someone calling the API, not for someone reading the source.

- **No internal implementation rationale.** Design tradeoffs ("why a dict and a list," "why not
  weak references," historical two-parameter designs) belong in an ADR or a commit message, not
  a docstring — they don't help someone calling the API, and they rot silently once the
  implementation moves on. This bit us once: `service.py`'s module docstring carried a 40-line
  "Architecture Notes" section that a docs audit had to strip out.
- **No private attributes.** Don't document `_leading_underscore` attributes in a class
  docstring's `Attributes:` section — they're not part of the contract.
- **Stick to standard Google-convention sections**: `Args`, `Returns`, `Raises`, `Yields`,
  `Attributes`, `Examples` (plural), `Note`, `Warning`, `Type Parameters`. Ruff's `D` rules
  and the griffe-based tooling (`poe api:check`, `scripts/update_context.py`) assume them,
  and invented headers (`Thread Safety:`, `Performance:`, `Use Cases:`, ...) repeated on
  every method are noise, not docs. Prefer folding a real constraint into prose or a single
  `Note:`.
- **Every code example must actually run.** Verify it in a scratch shell before committing it,
  the same way you'd verify one in `docs/`. This project has shipped broken examples before -
  missing `@dataclass` decorators, an undefined `resolver` variable, a `providers.Self()`
  self-registration pattern that recurses infinitely - all inside docstrings, none caught until
  someone ran them.
- Async (top-level `pymediate`) and sync (`pymediate.sync`) docstrings are structural mirrors,
  same as the code — if you fix or reword one, check the other side for the identical issue.
- `poe lint` enforces docstring presence/formatting (ruff's `D` rules, Google convention) on
  `src/pymediate/` excluding `_internal/`; it won't catch stale content or broken examples, so
  don't rely on it as the only check.

## The typing-snippet test system — do not "fix" these

`tests/typing/snippets/errors/*.py` are **deliberately type-invalid**. The cross-checker
harness (`test_mypy.py` + `test_basedpyright.py`, per issue #39) asserts every file in
`errors/` fails **both** mypy `--strict` and basedpyright (standard *and* recommended modes),
with the exact diagnostic per checker pinned in `tests/typing/expectations.py`. If you see a
type error in `errors/`, that's the test working correctly — never add `# type: ignore`,
never add them to `mypy.ini` or basedpyright-config exclusions, never "correct" the type
error. Adding/removing an errors case means updating both tables in `expectations.py`
(a sync test fails otherwise).

`valid/` snippets are held to the opposite bar: they must pass mypy `--strict`, produce
**zero errors and zero warnings** under basedpyright's recommended mode (use `@override` on
handler/behavior `__call__` overrides; consume `Services.add(...)` results by chaining into
`.provider()`), and **execute at runtime** (`test_snippets_runtime.py` — sync snippets run at
module level, async ones define `async def main()` and the harness runs it).

Config isolation: the mypy half runs with `--config-file tests/typing/mypy_snippets.ini`,
deliberately bypassing the repo-root `mypy.ini` — its `[mypy-tests.*]` suppressions
(`call-arg`, `arg-type`, ...) would otherwise apply to the snippets and mask exactly the
errors they exist to catch (this happened; see #39). Don't remove that flag or point the
snippets back at the root config. The basedpyright half uses the checked-in
`tests/typing/basedpyright_{standard,recommended}.json` configs, asserts an exact pinned
basedpyright version (`PINNED_BASEDPYRIGHT_VERSION` in `test_basedpyright.py` — bump it
together with `uv lock --upgrade-package basedpyright` and re-review the corpus), and gates
`basedpyright --verifytypes pymediate --ignoreexternal` at 100% public-API type completeness.
The flag excludes incomplete third-party stubs; PyMediate's own public symbols must still be
fully known.

## ADRs

Nontrivial design/API changes get a numbered ADR in `docs/adr/`, following the existing
template (Context → Investigation/Proposed Solutions → Pros/Cons → Decision → Consequences).
Existing ADRs (0001, 0002) were authored by Claude and reviewed by @sina-al (repo owner's GitHub
handle) — continue that pattern for anything touching public API shape, generics design, or
breaking changes. Use the `/adr` skill to scaffold a new one.

ADR 0002 revisits and overturns part of ADR 0001's decision (0001 rejected a single type
parameter for `PipelineBehavior`; 0002 later adopted one for the narrower case of selective
behaviors) — read both before assuming either alone reflects the current design.

## Issue tracking & the project board

Planning lives in GitHub Issues on `sina-al/pymediate`, mirrored onto the user-level
GitHub Project board **#2 "pymediate"** (<https://github.com/users/sina-al/projects/2>).
**All issue filing goes through the `edict` skill** — it owns the interview flow, the
issue template, labels, titles, and the board plumbing (project/field/option IDs).
Requests like "file an issue", "add this to the roadmap", "track this", or "put it on
the board" all mean invoking that skill, even for one-liners.

## Versioning

PyMediate follows [ZeroVer](https://0ver.org/): the major version stays at `0` indefinitely —
there's no planned 1.0. This is consistent with, not a workaround of, SemVer itself: SemVer's
own clause 4 says "Major version zero (0.y.z) is for initial development. Anything MAY change
at any time. The public API SHOULD NOT be considered stable."

Since major can never carry a signal, minor and patch split that job between them:

- **Minor** (`0.X.0`) — a breaking change to the public API, or a new backward-compatible
  feature. "Breaking" here means the same surfaces already called out in "Quality bar" below:
  a removed/changed name in `__init__.py`'s `__all__`, or a removed/changed public symbol in
  `RequestHandler` or the `ServiceProvider` protocol.
- **Patch** (`0.1.X`) — bug fixes, docs, refactors, tooling — anything with no public API impact.

The version exists **only as a git tag** — hatch-vcs derives it at build time, `__version__`
reads installed package metadata, and there are no version strings, bump commits, or
committed CHANGELOG.md in the repo (changelogs are rendered by git-cliff, config in
`cliff.toml`, into the release PR body and GitHub Release notes). A version that reached
TestPyPI is burned forever — the retry is the next version, never a re-upload.
`scripts/release_impact.py` (via `poe release:impact`) recommends minor-vs-patch by diffing
commits and the flagged API surface since the last tag; `prepare-release.yml -f bump=auto`
follows it.

## Branch/merge policy

Two long-lived branches — see `OPERATIONS.md` for the full model and enforcement inventory:

- **`main`** is the trunk and **may be red** — the maintainer pushes directly (ruleset
  bypass; that's lane 1, sanctioned, not a misconfiguration). Everyone else: PRs only,
  squash merge only (so the PR title *is* the commit message — Conventional Commits format
  enforced by `pr.yml`), required checks `Checks` / `Test Suite` / `Documentation` /
  `All Checks Passed`, CodeQL. Dependabot patch-level PRs auto-merge once green
  (`dependabot-automerge.yml`); minor/major wait for review.
- **`stable`** holds the released history: one merge commit per release, each tagged. Only
  release PRs (cut branches `release/vX.Y.Z` opened by `prepare-release.yml`) target it;
  merge commits only, required checks plus `Release Test Results`, **no bypass actors** —
  a red release PR cannot be merged without editing the ruleset itself.

branch-guard/tag-guard block branch and tag creation repo-wide — contributors work from
forks; only the maintainer, Dependabot, and the `pymediate-releaser` App can create
branches, and only the maintainer and the App can tag. The
`python-coverage-comment-action-data` branch is machine-managed (coverage badge data).

## Release process

Use the `/release` skill for the step-by-step checklist; `OPERATIONS.md` documents the
model. Short version: `gh workflow run prepare-release.yml -f bump=auto` opens a
zero-commit release PR (`release/vX.Y.Z` cut of main → `stable`) whose **diff is everything
since the last release** — reviewing it is the release review. Closing it is a
consequence-free rejection (the cut branch auto-deletes); merging it makes `tag-release.yml`
tag the merge commit, which runs `release.yml`: validate → build (+ provenance attestation)
→ install matrix + examples against the built wheel → TestPyPI → examples against the
TestPyPI artifact (`scripts/run_examples.py`) → the `pypi` environment's required-reviewer
gate → PyPI → examples smoke test against PyPI → GitHub Release last.

Release workflows authenticate as the `pymediate-releaser` GitHub App — short-lived
installation tokens minted per job via `actions/create-github-app-token` from the
`PYMEDIATE_RELEASER_APP_ID` repo variable and `PYMEDIATE_RELEASER_PRIVATE_KEY` secret. The
App identity (not `GITHUB_TOKEN`) is what makes the release PR trigger its required checks
and the tag-push trigger `release.yml`. Publishing uses Trusted Publishing (OIDC), no
stored credentials, registered on **both** pypi.org and test.pypi.org — separate services,
separate registrations. `release.yml` hard-fails if the tag doesn't match the version
hatch-vcs derives from the tagged checkout.

## Docs

`docs/` is a Next.js + Fumadocs app (pnpm, Node 22, static export) deployed to GitHub Pages
at <https://pymediate.sina-al.uk> from `main` via `docs.yml`. The API reference pages are
hand-written MDX that mirror the source docstrings — keep them in sync when the public API
or its docstrings change. App conventions, content layout, and the docs `poe` tasks live in
`docs/CLAUDE.md` (loaded automatically when working under `docs/`). `docs/adr/` sits
outside `content/` on purpose — ADRs are versioned with the repo but not published on
the site.

## API Signatures

@context/api-signatures.md

Generated from source by `uv run poe context:update` (`scripts/update_context.py`); run
`uv run poe context:check` to confirm it isn't stale. Don't hand-edit that file.
