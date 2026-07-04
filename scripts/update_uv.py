#!/usr/bin/env python3
"""Bump the pinned uv version.

Updates `required-version` under `[tool.uv]` in pyproject.toml — the single source of truth
also read automatically by astral-sh/setup-uv in CI (see comment in pyproject.toml) — and
upgrades the local `uv` install to match.

Usage:
    python3 scripts/update_uv.py                # bump to the latest uv release
    python3 scripts/update_uv.py 0.11.30         # bump to a specific version
    python3 scripts/update_uv.py --check         # print current vs. latest, exit 1 if behind
    python3 scripts/update_uv.py --skip-self-update  # only edit pyproject.toml
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"
REQUIRED_VERSION_PATTERN = re.compile(r'required-version\s*=\s*"==([^"]+)"')
GITHUB_LATEST_RELEASE_URL = "https://api.github.com/repos/astral-sh/uv/releases/latest"


def latest_uv_version() -> str:
    request = urllib.request.Request(
        GITHUB_LATEST_RELEASE_URL,
        headers={"Accept": "application/vnd.github+json"},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        data = json.load(response)
    return str(data["tag_name"]).lstrip("v")


def pinned_version() -> str | None:
    match = REQUIRED_VERSION_PATTERN.search(PYPROJECT.read_text())
    return match.group(1) if match else None


def set_pinned_version(version: str) -> None:
    text = PYPROJECT.read_text()
    new_line = f'required-version = "=={version}"'
    if REQUIRED_VERSION_PATTERN.search(text):
        text = REQUIRED_VERSION_PATTERN.sub(f'required-version = "=={version}"', text, count=1)
    elif "[tool.uv]" in text:
        text = text.replace("[tool.uv]", f"[tool.uv]\n{new_line}", 1)
    else:
        text = text.rstrip("\n") + f"\n\n[tool.uv]\n{new_line}\n"
    PYPROJECT.write_text(text)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "version", nargs="?", help="target uv version (default: latest from GitHub)"
    )
    parser.add_argument(
        "--skip-self-update",
        action="store_true",
        help="only edit pyproject.toml; don't run `uv self update`",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="print current vs. latest and exit 1 if out of date, without changing anything",
    )
    args = parser.parse_args()

    current = pinned_version()

    if args.check:
        latest = latest_uv_version()
        print(f"pinned: {current or '(none)'}  latest: {latest}")
        sys.exit(0 if current == latest else 1)

    target = args.version or latest_uv_version()

    if current == target:
        print(f"Already pinned to {target}, nothing to do.")
    else:
        set_pinned_version(target)
        print(f"pyproject.toml: required-version {current or '(none)'} -> {target}")

    if not args.skip_self_update:
        subprocess.run(["uv", "self", "update", target], check=True)


if __name__ == "__main__":
    main()
