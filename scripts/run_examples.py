#!/usr/bin/env python3
"""Run every example's tests against a specific pymediate release.

The release pipeline's examples stage (release.yml) calls this after publishing a release
candidate to TestPyPI. For each examples/<name>/ project (see examples/README.md for the
contract) it:

  1. copies the example to a temp directory (the checkout is never modified),
  2. appends an explicit uv index for the staging registry and pins pymediate's source to
     it — only pymediate resolves there; every other dependency still comes from real PyPI,
  3. re-pins the dependency to the exact release version (`uv add pymediate==X.Y.Z`),
  4. runs `uv run pytest`.

Exits non-zero if any example fails. Also usable locally against real PyPI to verify the
mechanism, e.g.:

    python3 scripts/run_examples.py --version 0.1.4 --index https://pypi.org/simple/
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLES_DIR = REPO_ROOT / "examples"
STAGING_INDEX_NAME = "release-staging"

INDEX_TEMPLATE = """
# Appended by scripts/run_examples.py (release pipeline): resolve pymediate — and only
# pymediate — from the staging index; everything else keeps coming from real PyPI.
[[tool.uv.index]]
name = "{name}"
url = "{url}"
explicit = true

[tool.uv.sources]
pymediate = {{ index = "{name}" }}
"""


@dataclass
class Result:
    example: str
    ok: bool
    detail: str = ""


def discover_examples() -> list[Path]:
    if not EXAMPLES_DIR.is_dir():
        return []
    return sorted(path.parent for path in EXAMPLES_DIR.glob("*/pyproject.toml") if path.is_file())


def check_contract(pyproject: Path) -> str | None:
    """Return a contract-violation message, or None if the example is runnable."""
    text = pyproject.read_text()
    if "[tool.uv.sources]" in text or "[[tool.uv.index]]" in text:
        return (
            "defines [tool.uv.sources] or [[tool.uv.index]]; the examples contract "
            "reserves those for this runner (see examples/README.md)"
        )
    if "pymediate" not in text:
        return "does not depend on pymediate"
    return None


def run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    print(f"  $ {' '.join(cmd)}", flush=True)
    # Drop any inherited VIRTUAL_ENV (e.g. the repo's own .venv when run via poe) so uv
    # targets the example workspace's environment, not the caller's.
    env = {key: value for key, value in os.environ.items() if key != "VIRTUAL_ENV"}
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, env=env)


def run_example(example: Path, version: str, index_url: str, workdir: Path) -> Result:
    name = example.name
    print(f"\n=== {name} ===", flush=True)

    violation = check_contract(example / "pyproject.toml")
    if violation:
        return Result(name, ok=False, detail=f"contract violation: {violation}")

    workspace = workdir / name
    # Exclude transient local state: a copied .venv has broken interpreter symlinks, and a
    # fresh sync in the workspace recreates it anyway.
    shutil.copytree(
        example,
        workspace,
        ignore=shutil.ignore_patterns(".venv", "__pycache__", ".pytest_cache"),
    )
    with (workspace / "pyproject.toml").open("a") as fp:
        fp.write(INDEX_TEMPLATE.format(name=STAGING_INDEX_NAME, url=index_url))

    steps = [
        ["uv", "add", f"pymediate=={version}"],
        ["uv", "sync"],
        ["uv", "run", "pytest"],
    ]
    for cmd in steps:
        proc = run(cmd, cwd=workspace)
        sys.stdout.write(proc.stdout)
        sys.stderr.write(proc.stderr)
        if proc.returncode != 0:
            return Result(name, ok=False, detail=f"`{' '.join(cmd)}` exited {proc.returncode}")
    return Result(name, ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--version", required=True, help="Exact pymediate version to test, e.g. 0.2.0"
    )
    parser.add_argument(
        "--index",
        default="https://test.pypi.org/simple/",
        help="Simple-API index URL that hosts that version (default: TestPyPI)",
    )
    args = parser.parse_args()

    examples = discover_examples()
    if not examples:
        print("No examples/*/pyproject.toml found — nothing to run.")
        return 0

    with tempfile.TemporaryDirectory(prefix="pymediate-examples-") as tmp:
        results = [run_example(path, args.version, args.index, Path(tmp)) for path in examples]

    width = max(len(result.example) for result in results)
    print(f"\nExamples against pymediate=={args.version} ({args.index}):")
    for result in results:
        status = "PASS" if result.ok else "FAIL"
        suffix = f"  ({result.detail})" if result.detail else ""
        print(f"  {result.example:<{width}}  {status}{suffix}")

    return 0 if all(result.ok for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
