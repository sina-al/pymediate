#!/usr/bin/env python3
"""Regenerate CHANGELOG.md (and its docs/changelog.md mirror) via git-cliff.

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

It also regenerates docs/changelog.md from the same output, so that page can't drift from
the real CHANGELOG.md the way it once did — that mirror used to be updated by hand, which is
exactly the kind of easy-to-forget manual step that caused the original bug this script fixes.

Usage:
    python3 scripts/generate_changelog.py
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CHANGELOG = REPO_ROOT / "CHANGELOG.md"
DOCS_CHANGELOG = REPO_ROOT / "docs" / "changelog.md"

DOCS_HEADER = """# Changelog

This page mirrors the [CHANGELOG.md](https://github.com/sina-al/pymediate/blob/main/CHANGELOG.md) \
at the repository root, which is generated from Conventional Commits with \
[git-cliff](https://git-cliff.org/) on each release. It's regenerated automatically by \
`uv run poe changelog` — don't hand-edit it.

"""


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


def write_docs_mirror(changelog_text: str) -> None:
    """Derive docs/changelog.md from the root CHANGELOG.md's rendered content."""
    # Drop the root file's own header (its "do not hand-edit above the first entry" note is
    # about the root file, not this mirror) and start from the first version/Unreleased heading.
    body = changelog_text[changelog_text.index("## [") :]
    # git-cliff's template leaves a blank line between every bullet, and two blank lines
    # between the last bullet of a group and the next "### Group" heading. Collapse both to a
    # single blank line so lists and sections render tightly, without touching the one blank
    # line that should separate a heading from what follows it.
    body = re.sub(r"(\n- [^\n]*)\n\n(?=- )", r"\1\n", body)
    body = re.sub(r"\n{3,}", "\n\n", body)
    DOCS_CHANGELOG.write_text(DOCS_HEADER + body)


def main() -> None:
    version = current_version()
    tag = f"v{version}"

    cmd = ["uvx", "git-cliff", "--output", str(CHANGELOG)]
    if tag_exists(tag):
        print(f"{tag} already exists - regenerating from real tag history (no --tag override).")
    else:
        print(f"{tag} not tagged yet - generating its changelog section as {tag}.")
        cmd += ["--tag", tag]

    subprocess.run(cmd, check=True)
    write_docs_mirror(CHANGELOG.read_text())
    print(f"Synced {DOCS_CHANGELOG.relative_to(REPO_ROOT)} from {CHANGELOG.name}.")


if __name__ == "__main__":
    main()
