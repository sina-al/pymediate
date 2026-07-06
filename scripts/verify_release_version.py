#!/usr/bin/env python3
"""Verify release version consistency between tag, pyproject.toml, and __init__.py."""

from __future__ import annotations

import argparse
import re
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT_FILE = REPO_ROOT / "pyproject.toml"
INIT_FILE = REPO_ROOT / "src" / "pymediate" / "__init__.py"
INIT_VERSION_PATTERN = re.compile(r'__version__\s*=\s*"([^"]+)"')


def normalize_tag(tag: str) -> str:
    """Return tag value with an optional leading 'v' removed."""
    return tag[1:] if tag.startswith("v") else tag


def read_pyproject_version() -> str:
    """Read the project version from pyproject.toml."""
    data = tomllib.loads(PYPROJECT_FILE.read_text())
    return str(data["project"]["version"])


def read_init_version() -> str:
    """Read __version__ from src/pymediate/__init__.py."""
    match = INIT_VERSION_PATTERN.search(INIT_FILE.read_text())
    if match is None:
        raise SystemExit(f"Couldn't find __version__ in {INIT_FILE}")
    return match.group(1)


def main() -> None:
    """Run release version consistency checks."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True, help="Release tag (e.g. v0.2.0 or 0.2.0)")
    args = parser.parse_args()

    tag_version = normalize_tag(args.tag)
    pyproject_version = read_pyproject_version()
    init_version = read_init_version()

    print(f"Tag version: {tag_version}")
    print(f"pyproject.toml version: {pyproject_version}")
    print(f"__init__.py version: {init_version}")

    if tag_version != pyproject_version:
        raise SystemExit("Error: Tag version doesn't match pyproject.toml")

    if tag_version != init_version:
        raise SystemExit("Error: Tag version doesn't match __init__.py")


if __name__ == "__main__":
    main()
