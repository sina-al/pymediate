# ADR 0013: Examples validation boundary

**Status:** Proposed
**Date:** 2026-07-18
**Author:** Claude
**Reviewers:** @sina-al

## Context

ADR 0007 made the examples gallery a downstream release-verification suite. The gallery now
contains 30 standalone uv projects. A validation run must discover those projects, reject
contract violations, copy each project without local state, replace its PyMediate dependency
with a wheel or an exact index version, and aggregate test failures.

The release workflows invoke the runner in several contexts:

```bash
uv run poe examples:test --wheel dist/*.whl
uv run poe examples:test --version "$VERSION" --index "$INDEX"
```

Before this decision, ordinary pull requests did not invoke the examples suite. Similar setup
steps also appear in the main checks, release pull request, and release workflows. This raises
two separate questions:

1. Should GitHub Actions own the validation logic instead of `scripts/run_examples.py`?
2. Should the repeated Actions setup be hidden behind a reusable workflow?

The boundary matters because the same validation must run locally and in GitHub Actions, while
workflow concerns such as event filters, permissions, artifacts, publish gates, and environments
exist only in GitHub Actions.

## Proposed Solution(s)

### Option A: Replace the Python runner with a reusable workflow

Move discovery, contract checks, dependency replacement, and test execution into a workflow
called through `workflow_call`. Use a matrix to run example projects in parallel.

**Pros:**

- Matrix jobs give each example a separate check and log.
- GitHub can run projects in parallel without adding concurrency to the runner.
- Action setup is declared in one workflow.

**Cons:**

- Local validation no longer uses the same entry point as CI.
- Discovery and TOML edits would become shell or embedded scripts inside YAML, or would still
  require a separate program. The reusable workflow would therefore move orchestration, not
  remove the validation code.
- Wheel artifacts, index waits, and release prerequisites differ between call sites. A reusable
  workflow would need inputs and conditionals for those differences.
- Reusable workflows operate at job granularity. They cannot extract only the repeated setup
  steps from an existing release job.
- Release control flow becomes split between the caller and called workflow, making publish
  gates harder to review in one file.

### Option B: Keep the Python runner and repeat each Actions job

Keep all discovery and validation in `scripts/run_examples.py`. Let every workflow perform its
own checkout, uv setup, artifact preparation, and runner invocation.

**Pros:**

- Local and CI runs use the same implementation.
- Each workflow shows its complete permissions, prerequisites, and failure boundary.
- The runner remains independent of GitHub Actions.

**Cons:**

- Checkout and uv setup are repeated.
- A new validation target must be added deliberately to each relevant workflow.
- The runner executes projects sequentially.

### Option C: Keep a portable runner with explicit Actions orchestration

Keep project-level logic in Python and give it four targets:

- `--check-contract` for static release-contract checks;
- `--check-repository` for names, README structure and links, editor files, devcontainers,
  and workspace coverage;
- `--wheel PATH` for a local or downloaded wheel;
- `--version X.Y.Z --index URL` for a published package.

Use GitHub Actions only for event and path filters, permissions, wheel construction or download,
index propagation waits, environments, and release gates. Relevant pull requests to `main` run
both check targets and then the complete gallery against a wheel. The four release gates from ADR
0007 remain explicit in their existing workflows.

Do not add a reusable workflow yet. The current wheel call sites have different artifact
preparation, and the index call sites sit on different sides of publish and environment gates.
If three or more call sites later share the same inputs, artifacts, and prerequisites, extract
that whole job at that point. If only setup steps repeat, a composite action is the closer GitHub
Actions abstraction, but it is not needed for the current amount of setup.

**Pros:**

- Developers can reproduce contract, wheel, and index failures from the command line.
- TOML handling, temporary copies, source exceptions, and result aggregation stay testable as
  Python code.
- Workflow files retain the release ordering and permissions that apply only to GitHub.
- Main-branch changes receive the same downstream wheel check before release preparation.
- The design can add a matrix later without moving validation rules into YAML.

**Cons:**

- A small amount of Actions setup remains repeated.
- The complete gallery still runs sequentially within one job.
- Changes to runner targets may require corresponding workflow and operations-document updates.

## Decision

Adopt Option C.

- `scripts/run_examples.py` remains the source of executable validation behavior.
- GitHub Actions owns triggers, path filtering, permissions, artifacts, environments, and gates.
- The Checks workflow runs both static check targets and `--wheel` for relevant pull requests
  to `main`.
- Release pull request and release workflow jobs remain explicit because their preparation and
  failure consequences differ.
- A reusable workflow is deferred until at least three callers have the same complete job
  contract. Similar command text alone is not sufficient.

## Consequences

### Positive

- The release contract and repository structure have fast, local commands and a CI gate.
- Every relevant main-branch change is tested against a built artifact before it merges.
- Release validation remains readable in the workflow that controls each publish boundary.
- Future parallel execution can call the same runner for one selected example rather than
  rewriting contract logic in YAML.

### Negative

- Relevant main pull requests take longer because they build a wheel and run all examples.
- GitHub Actions setup remains in more than one workflow.
- Sequential execution may need revisiting as the gallery grows.

## Migration Path

No user migration is needed. Maintainers use the two check targets for static validation and
keep using the existing wheel and version commands. The Checks workflow adds the new
main-branch gate.

## Open Questions

- When should the suite become a matrix? Tentative threshold: when sequential wall-clock time
  becomes a regular source of CI delay. Add a project selector or machine-readable discovery
  output to the runner before introducing the matrix.
- Should documentation-only changes run the wheel suite? Tentative answer: yes while the suite
  remains short enough, because README commands and project files are one maintained example.
- Should the two static check targets eventually become one command? Tentative answer: keep
  them separate so release-contract failures are distinct from repository presentation and
  editor-configuration failures.
- Should declared lower-bound compatibility become a separate runner target? The contract
  check validates requirement syntax, while wheel and index runs deliberately replace that
  requirement. Until a historical-version mode is added, the earliest-compatible-release
  claim remains a maintainer review responsibility.
