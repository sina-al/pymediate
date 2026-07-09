---
name: release
description: Cut a versioned release of pymediate — dispatch the Prepare Release workflow, review and merge the release PR into stable, then approve the PyPI environment gate. Use when asked to release, publish, or cut/ship a new version.
---

# /release — cut a versioned release

The release process is workflow-driven and human-in-the-loop; `OPERATIONS.md` is the full
reference for the model (two-branch, tag-derived versions, burned-version retries). The
logic lives in `prepare-release.yml`, `tag-release.yml`, `release.yml`,
`scripts/release_impact.py`, `scripts/run_examples.py`, and `cliff.toml` — this skill is a
checklist through them.

**Publishing is irreversible** (a version that reaches TestPyPI or PyPI is burned forever,
even if deleted) — confirm the version and changelog with the user at the release-PR
stage. Don't merge a release PR silently as part of a larger task.

## Flow overview

```
gh workflow run prepare-release.yml -f bump=auto   (maintainer-only)
        │  computes next version from last tag, pushes zero-commit cut branch
        │  release/vX.Y.Z at main HEAD, opens PR into stable
        ▼
release PR  "chore(release): vX.Y.Z"    ← human-in-the-loop #1: review & merge
        │  the PR diff = everything since the last release; body has the changelog
        │  and impact report; comments carry test/coverage/audit reports
        │  (close instead = consequence-free rejection; cut branch auto-deletes)
        │  merge (MERGE COMMIT) → tag-release.yml tags the merge commit vX.Y.Z
        ▼
release.yml   validate → build(+attest) → test-install → TestPyPI → examples
        │
        ▼
pypi environment approval                ← human-in-the-loop #2: approve in Actions UI
        │  (only reachable if TestPyPI and the examples suite succeeded)
        ▼
PyPI → GitHub Release (created last)
```

## Pre-flight

- Confirm there are unreleased commits worth shipping: `git log $(git describe --tags
  --abbrev=0)..origin/main --oneline`. main does NOT need to be green — the release PR's
  checks are the gate, so a red main simply produces an unmergeable release PR.
- No other release PR should be mid-review (dispatching auto-closes superseded ones — warn
  the user if one is open).
- One-time infrastructure that must already exist (stop and tell the user if not):
  Trusted Publishers registered on both pypi.org and test.pypi.org for `sina-al/pymediate`
  / `release.yml` / environments `pypi`/`testpypi`; the `pymediate-releaser` App installed
  with `PYMEDIATE_RELEASER_APP_ID` (variable) and `PYMEDIATE_RELEASER_PRIVATE_KEY` (secret),
  and kept as a tag-guard + branch-guard bypass actor.

## Steps

1. **Dispatch:**
   ```bash
   gh workflow run prepare-release.yml -f bump=auto   # or bump=patch / bump=minor
   ```
   `auto` follows `release:impact`'s `RECOMMENDATION:` (commit classification + AST diff
   of the flagged API surfaces). It's a heuristic — the PR body includes the full report
   so you can second-guess it. If the user wants a different kind after seeing the PR,
   just re-dispatch with `bump=minor|patch`; the old PR is superseded automatically.

2. **Review the release PR** (`chore(release): vX.Y.Z`, base `stable`). Check:
   - The bump kind matches the impact report's reasoning — present both to the user and
     get explicit confirmation before merging.
   - The changelog section in the PR body is complete and correctly categorized.
   - The diff (everything since the last release) contains nothing the user doesn't want
     to ship — this is the only review that lane-1 direct pushes ever get.
   - All checks green, including "Release Test Results" and "Examples" (every
     examples/ project against a wheel built from the cut — if this is red on a
     breaking release, the examples on main need updating first; close, fix, re-dispatch).

3. **Merge with a merge commit** (required; squash is blocked on stable):
   ```bash
   gh pr merge <n> --merge
   ```
   stable-guard requires no approval count, so this needs no admin bypass — if it won't
   merge, a required check is failing; do NOT bypass it. Merging is the point of no
   return for the tag: `tag-release.yml` tags the merge commit, starting `release.yml`.

4. **Watch the pipeline:**
   ```bash
   gh run watch $(gh run list --workflow=release.yml --limit 1 --json databaseId --jq '.[0].databaseId')
   ```
   Order: `validate-release` (full suite + tag-vs-hatch-vcs version check) →
   `build-package` (+ provenance attestation) → `test-install` (3 OS × 3 Pythons) →
   `publish-testpypi` → `examples` (each examples/ project against the TestPyPI artifact)
   → **waits at the `pypi` environment** → `publish-pypi` → `create-release`.

5. **Approve the PyPI publish** at the `pypi` environment gate from the run page. This is
   the final confirmation — unreachable unless TestPyPI and the examples suite succeeded.

6. **Verify:**
   - `https://pypi.org/project/pymediate/` shows the new version.
   - GitHub Release exists at `.../releases/tag/vX.Y.Z` with changelog notes and dist files.
   - `gh attestation verify <wheel> -R sina-al/pymediate` passes (download from the Release).
   - Optionally, scratch venv: `pip install pymediate==X.Y.Z` + smoke import.

## If something fails partway

- **Before TestPyPI**: nothing is burned. Fix and `gh run rerun <run-id> --failed`, or
  close/re-dispatch — both safe.
- **At/after TestPyPI** (failed examples, workflow bug, user rejects at the gate): that
  version is burned. Land any fix on main, re-dispatch `prepare-release.yml`; the version
  computation skips existing tags automatically, so the next PR proposes the next free
  version. Never try to reuse a burned version.
- A tag for a never-published version may remain — expected under the burn policy; the
  GitHub Release is only created after PyPI succeeds, so nothing user-facing dangles.

## Manual fallback

If workflows are unavailable: `git tag vX.Y.Z <sha-on-stable> && git push origin vX.Y.Z`
(maintainer clears tag-guard) starts `release.yml` directly; or dispatch it on a tag ref:
`gh workflow run release.yml --ref vX.Y.Z`. Dispatching on a branch ref fails the version
check by design. Only tag commits on `stable` that a merged release PR produced.
