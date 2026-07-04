#!/usr/bin/env python3
"""Bump pymediate's version consistently across pyproject.toml and __init__.py.

`uv version` (astral-sh/uv's own release-version command) only touches pyproject.toml —
uv_build has no dynamic-versioning support (unlike Hatchling), so this wraps it and syncs
src/pymediate/__init__.py's __version__ to match. release.yml's "Verify version consistency"
step checks both of these against the git tag at release time.

Usage:
    python3 scripts/bump_version.py patch          # 0.1.0 -> 0.1.1
    python3 scripts/bump_version.py minor          # 0.1.0 -> 0.2.0
    python3 scripts/bump_version.py major          # 0.1.0 -> 1.0.0
    python3 scripts/bump_version.py 0.2.0          # set an explicit version
    python3 scripts/bump_version.py patch --dry-run
"""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

INIT_PY = Path(__file__).resolve().parent.parent / "src" / "pymediate" / "__init__.py"
VERSION_PATTERN = re.compile(r'__version__\s*=\s*"([^"]+)"')
BUMP_KINDS = {"major", "minor", "patch", "stable", "alpha", "beta", "rc", "post", "dev"}


def current_uv_version() -> str:
    result = subprocess.run(
        ["uv", "version", "--short"], capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def set_init_version(version: str) -> None:
    text = INIT_PY.read_text()
    if not VERSION_PATTERN.search(text):
        raise SystemExit(f"Couldn't find __version__ in {INIT_PY}")
    INIT_PY.write_text(VERSION_PATTERN.sub(f'__version__ = "{version}"', text, count=1))


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("target", help="a bump kind (major/minor/patch/...) or an explicit version")
    parser.add_argument(
        "--dry-run", action="store_true", help="show the new version without writing anything"
    )
    args = parser.parse_args()

    uv_version_cmd = ["uv", "version"]
    uv_version_cmd += ["--bump", args.target] if args.target in BUMP_KINDS else [args.target]

    if args.dry_run:
        subprocess.run([*uv_version_cmd, "--dry-run"], check=True)
        return

    before = current_uv_version()
    subprocess.run(uv_version_cmd, check=True)
    after = current_uv_version()

    if before != after:
        set_init_version(after)
        print(f"src/pymediate/__init__.py: __version__ {before} -> {after}")

    print(f"Version bumped: {before} -> {after}. Review the diff, then commit and tag v{after}.")


if __name__ == "__main__":
    main()
