---
name: release
description: Cut a versioned release of pymediate — bump the version, regenerate the changelog, tag, and push, which triggers release.yml's test -> build -> GitHub Release -> TestPyPI -> PyPI pipeline. Use when asked to release, publish, or cut/ship a new version.
---

# /release — cut a versioned release

All the real logic lives in `scripts/bump_version.py`, `cliff.toml`, and `release.yml` — this
skill is a checklist through them, not a re-description of what they do. See `CLAUDE.md`'s
"Release process" section for the underlying mechanics (why the version is hand-synced in two
places, why TestPyPI gates PyPI, etc.).

**Tagging and pushing a release is irreversible-adjacent** (a version can never be re-uploaded
to PyPI once published) — confirm the version and changelog with the user before pushing the
tag. Don't do it silently as part of a larger task.

## Pre-flight

- Confirm you're on `main`, the working tree is clean (`git status`), and the latest commit on
  `origin/main` has green CI (Tests / Code Quality / Documentation) — check with `gh run list`.
- If this is the **first-ever release**: a Trusted Publisher must already be registered on both
  pypi.org and test.pypi.org for `sina-al/pymediate`, workflow `release.yml`, environments
  `pypi` / `testpypi` respectively (one-time, manual, on PyPI's own site — nothing in this repo
  can do it). If that's not done yet, stop and tell the user, don't tag.

## Steps

1. **Bump the version.** Preview first, then apply:
   ```bash
   uv run poe version:bump patch --dry-run   # or minor / major / an explicit X.Y.Z
   uv run poe version:bump patch
   ```
   This updates `pyproject.toml` and `src/pymediate/__init__.py` together (see `scripts/bump_version.py`).

2. **Regenerate the changelog:**
   ```bash
   uv run poe changelog
   ```
   git-cliff only headers a version once a matching tag exists in git — since this step runs
   *before* tagging (step 4), a bare `git-cliff` invocation here would dump the new release's
   commits under a permanent `[Unreleased]` heading instead of `[X.Y.Z]` (this happened for real
   in v0.1.1 — see `scripts/generate_changelog.py`'s docstring). The `changelog` task wraps
   git-cliff with `--tag vX.Y.Z` (the version just bumped in step 1) specifically to avoid this,
   falling back to plain git-cliff if that tag somehow already exists. Skim the new
   `CHANGELOG.md` entry after running it — confirm it's headed `## [X.Y.Z] - <date>`, not
   `## [Unreleased]`, and that nothing landed in the catch-all "Other" group that should've been
   categorized.

3. **Review and commit:**
   ```bash
   git diff
   git add pyproject.toml src/pymediate/__init__.py CHANGELOG.md uv.lock
   git commit -m "chore(release): vX.Y.Z"
   git push origin main
   ```
   (`uv.lock` may or may not have changed — include it only if `git diff` shows it did.)

4. **Tag and push** — this is what actually triggers `release.yml`:
   ```bash
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```
   `workflow_dispatch` also exists on `release.yml` but is currently non-functional (its
   `version` input is unwired, and the version-consistency check reads `github.ref_name`, which
   is a branch name, not a version, on a manual trigger) — the tag push above is the only
   reliable path right now.

5. **Watch the pipeline:**
   ```bash
   gh run watch $(gh run list --workflow=release.yml --limit 1 --json databaseId --jq '.[0].databaseId')
   ```
   Job order: `validate-release` (tests/type/lint + tag-vs-file version check) →
   `build-package` → `test-install` (wheel install across 3 OSes × 3 Python versions) →
   `create-release` (GitHub Release + git-cliff notes) → `publish-testpypi` → `publish-pypi`.
   TestPyPI gates the real publish — if it fails, PyPI is never touched.

6. **Verify after it's green:**
   - GitHub Release exists at `https://github.com/sina-al/pymediate/releases/tag/vX.Y.Z` with
     the right notes attached.
   - `https://pypi.org/project/pymediate/` shows the new version.
   - `CHANGELOG.md` on `main` has a real `## [X.Y.Z] - <date>` section for this release (not
     still sitting under `## [Unreleased]`) — this is the step 2 check again, but re-confirm it
     post-push since that's the actual persisted file readers see.
   - `docs/changelog.md` matches the root `CHANGELOG.md` — it's a manually-synced mirror (see
     its own header), so update it too if you haven't.
   - Optionally, in a scratch venv: `pip install pymediate==X.Y.Z` and a quick smoke import.

## If something fails partway

Each job only runs once its dependencies succeed, and nothing is retried automatically. Fix the
underlying issue, then re-run the specific failed job from the Actions UI or
`gh run rerun <run-id> --failed` — re-running is safe since none of the steps are destructive
(PyPI/TestPyPI publishes of the same version simply fail again rather than double-publishing).
The one exception: if `publish-testpypi` or `publish-pypi` partially succeeded then a later step
failed, that version is now stuck on that index — bump to the next patch version rather than
trying to reuse it.
