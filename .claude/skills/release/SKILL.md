---
name: release
description: Cut a versioned release of pymediate — dispatch the Prepare Release workflow, review and merge the release PR it opens, then approve the PyPI environment gate. Use when asked to release, publish, or cut/ship a new version.
---

# /release — cut a versioned release

The release process is workflow-driven and human-in-the-loop. The real logic lives in
`prepare-release.yml`, `tag-release.yml`, `release.yml`, `scripts/bump_version.py`,
`scripts/release_impact.py`, and `cliff.toml` — this skill is a checklist through them.
See `CLAUDE.md`'s "Versioning" section for the minor-vs-patch policy (PyMediate follows
[ZeroVer](https://0ver.org/) — major never moves).

**Publishing is irreversible** (a version can never be re-uploaded to PyPI once published) —
confirm the version and changelog with the user at the release-PR stage. Don't merge a
release PR silently as part of a larger task.

## Flow overview

```
gh workflow run prepare-release.yml     (maintainer-only: dispatch needs write access)
        │  runs release:impact, bumps version, regenerates CHANGELOG.md
        ▼
release PR  "chore(release): vX.Y.Z"    ← human-in-the-loop #1: review & merge
        │  merge (squash) → tag-release.yml tags the squash commit as vX.Y.Z
        ▼
release.yml   validate → build → test-install → GitHub Release → TestPyPI
        │
        ▼
pypi environment approval                ← human-in-the-loop #2: approve in Actions UI
        │  (only reachable if TestPyPI succeeded)
        ▼
PyPI
```

## Pre-flight

- Confirm `main` is green (`gh run list`) and there are unreleased commits worth shipping.
- If this is the **first-ever release**: a Trusted Publisher must already be registered on
  both pypi.org and test.pypi.org for `sina-al/pymediate`, workflow `release.yml`,
  environments `pypi` / `testpypi` respectively (one-time, manual, on PyPI's own site).
  If that's not done yet, stop and tell the user, don't dispatch.
- The `RELEASE_PR_TOKEN` repo secret (fine-grained PAT: this repo, contents +
  pull-requests write) must exist and be unexpired — `prepare-release.yml` and
  `tag-release.yml` both fail without it.

## Steps

1. **Dispatch the prepare workflow:**
   ```bash
   gh workflow run prepare-release.yml -f bump=auto   # or bump=patch / bump=minor
   ```
   `auto` follows `release:impact`'s `RECOMMENDATION:` line (commit classification +
   AST diff of the flagged API surfaces). It's a heuristic over a diff, not a guarantee —
   the release PR body includes the full report so you can second-guess it.

2. **Review the release PR** it opens (`chore(release): vX.Y.Z` from branch
   `release/vX.Y.Z`). Check:
   - The bump kind matches the impact report's reasoning (present both to the user and
     get explicit confirmation before merging).
   - `CHANGELOG.md`'s new entry is headed `## [X.Y.Z] - <date>`, **not** `## [Unreleased]`,
     and nothing landed in the catch-all "Other" group that should've been categorized.
   - Wait for the PR's checks to go green.

3. **Merge the release PR.** Note: as a solo maintainer you can't approve your own PR
   (the PAT authors it as you), so the required-approval rule can only be satisfied by
   bypass — merge with `gh pr merge <n> --squash --admin` *after* visually confirming the
   checks are green. Merging is the point of no return for the tag: `tag-release.yml`
   immediately tags the squash commit, which starts `release.yml`.

4. **Watch the pipeline:**
   ```bash
   gh run watch $(gh run list --workflow=release.yml --limit 1 --json databaseId --jq '.[0].databaseId')
   ```
   Job order: `validate-release` (full tests/type/lint + tag-vs-file version check) →
   `build-package` → `test-install` (wheel install across 3 OSes × 3 Pythons) →
   `create-release` (GitHub Release + git-cliff notes) → `publish-testpypi` →
   **waits at the `pypi` environment** → `publish-pypi`.

5. **Approve the PyPI publish.** Once TestPyPI has succeeded, the `publish-pypi` job sits
   pending on the `pypi` environment's required-reviewer gate. Approve it from the run
   page (or `gh run view` → the review URL). This is the final confirmation — TestPyPI
   failing means this gate is never even reachable.

6. **Verify after it's green:**
   - GitHub Release exists at `https://github.com/sina-al/pymediate/releases/tag/vX.Y.Z`.
   - `https://pypi.org/project/pymediate/` shows the new version.
   - `CHANGELOG.md` on `main` has the real `## [X.Y.Z] - <date>` section.
   - Optionally, in a scratch venv: `pip install pymediate==X.Y.Z` + smoke import.

## Manual fallback (the old tag-push flow)

If the workflows are unavailable, the pre-automation flow still works — run steps locally
(`poe release:impact`, `poe version:bump`, `poe changelog`), commit to `main` (admin
bypass), then `git tag vX.Y.Z && git push origin vX.Y.Z` (tag-guard permits the
maintainer). Alternatively dispatch `release.yml` directly **on a tag ref**:
`gh workflow run release.yml --ref vX.Y.Z` — dispatching it on a branch ref fails the
version-consistency check by design.

## If something fails partway

Each job only runs once its dependencies succeed; nothing retries automatically. Fix the
issue, then `gh run rerun <run-id> --failed` — re-running is safe (PyPI/TestPyPI publishes
of the same version fail rather than double-publish). The one exception: if a publish job
partially succeeded, that version is stuck on that index — cut the next patch version
rather than reusing it. If `prepare-release.yml` produced a bad release PR, close it
unmerged and delete the `release/vX.Y.Z` branch; nothing has been tagged yet.
