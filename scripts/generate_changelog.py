#!/usr/bin/env python3
"""Regenerate CHANGELOG.md via git-cliff.

git-cliff only creates a "[X.Y.Z] - date" heading for commits once a matching git tag
actually exists in history. The release flow (see the /release skill) bumps the version
and regenerates the changelog *before* creating the tag, so a plain `git-cliff` invocation
at that point has no tag to key off yet and silently dumps the new release's commits under
a permanent "[Unreleased]" heading instead — this happened for real in v0.1.1.

This script passes git-cliff `--tag vX.Y.Z` using the version currently in pyproject.toml,
which tells it to label the not-yet-tagged commits as that release. It only does this when
that tag doesn't already exist, so re-running the task after the tag has been pushed (or at
any other time) safely falls back to plain git-cliff behavior instead of relabeling history
or creating a duplicate version heading.

Usage:
    python3 scripts/generate_changelog.py
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CHANGELOG = REPO_ROOT / "CHANGELOG.md"


def current_version() -> str:
    result = subprocess.run(
        ["uv", "version", "--short"], capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def tag_exists(tag: str) -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "-q", "--verify", f"refs/tags/{tag}"],
        capture_output=True,
    )
    return result.returncode == 0


def main() -> None:
    version = current_version()
    tag = f"v{version}"

    # --include-path keeps the changelog to changes in the shipped package: a commit that
    # only touched docs/, scripts/, .github/, or the README never reaches an installed
    # `pip install pymediate`, so it shouldn't appear in the user-facing changelog. (This
    # is the same src/pymediate/** lens release_impact.py uses to decide what counts as a
    # feature.) Version-section boundaries are preserved under the filter.
    cmd = ["uvx", "git-cliff", "--include-path", "src/pymediate/**", "--output", str(CHANGELOG)]
    if tag_exists(tag):
        print(f"{tag} already exists - regenerating from real tag history (no --tag override).")
    else:
        print(f"{tag} not tagged yet - generating its changelog section as {tag}.")
        cmd += ["--tag", tag]

    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
