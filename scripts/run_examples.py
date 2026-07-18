#!/usr/bin/env python3
"""Run every example's tests against a specific pymediate build.

Two modes, covering the four examples stages of the release flow (see OPERATIONS.md and
examples/README.md):

  --wheel PATH      Test against a locally built wheel. Used by the release PR's required
                    "Examples" check (release-pr-report.yml), where breaking changes that
                    stale examples can't absorb fail *before* merge — no tag, no burned
                    version — and again by release.yml against the freshly built release
                    artifact, before anything is published.

  --version X.Y.Z   Test against a published release on an index (default TestPyPI). Used
    [--index URL]   by release.yml after the TestPyPI publish to validate the real
                    publish-and-install path, and after the PyPI publish to smoke-test the
                    exact artifact users install. Only pymediate resolves from the given
                    index; every other dependency still comes from real PyPI.

Either way, each examples/<name>/ project is copied to a temp directory (the checkout is
never modified), re-pinned to the build under test, and its tests run via `uv run pytest`.
Exits non-zero if any example fails. Also usable locally, e.g.:

    python3 scripts/run_examples.py --version 0.1.5 --index https://pypi.org/simple/
    uv build && python3 scripts/run_examples.py --wheel dist/pymediate-*.whl
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLES_DIR = REPO_ROOT / "examples"
STAGING_INDEX_NAME = "release-staging"
FLAGSHIP_EXAMPLE = "100-hexagonal-architecture"
FLAGSHIP_PYMEDIATE_SOURCE = {"path": "../..", "editable": True}
FLAGSHIP_PYMEDIATE_SOURCE_LINE = 'pymediate = { path = "../..", editable = true }\n'


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
    if "[[tool.uv.index]]" in text:
        return (
            "defines [[tool.uv.index]]; the examples contract reserves indexes for this runner "
            "(see examples/README.md)"
        )
    sources = tomllib.loads(text).get("tool", {}).get("uv", {}).get("sources", {})
    invalid_sources = {}
    for name, source in sources.items():
        is_flagship_checkout = (
            pyproject.parent.name == FLAGSHIP_EXAMPLE
            and name == "pymediate"
            and source == FLAGSHIP_PYMEDIATE_SOURCE
            and text.count(FLAGSHIP_PYMEDIATE_SOURCE_LINE) == 1
        )
        if not is_flagship_checkout and (name == "pymediate" or source != {"workspace": True}):
            invalid_sources[name] = source
    if invalid_sources:
        return (
            "defines a non-workspace [tool.uv.sources] entry; only internal "
            "{ workspace = true } sources and the flagship's exact local pymediate source "
            "are allowed"
        )
    if "pymediate" not in text:
        return "does not depend on pymediate"
    return None


def copy_example_for_release(example: Path, workspace: Path) -> None:
    """Copy one example and remove the flagship's checkout-only source override."""
    shutil.copytree(
        example,
        workspace,
        ignore=shutil.ignore_patterns(".venv", "__pycache__", ".pytest_cache"),
    )
    if example.name != FLAGSHIP_EXAMPLE:
        return

    pyproject = workspace / "pyproject.toml"
    text = pyproject.read_text()
    if text.count(FLAGSHIP_PYMEDIATE_SOURCE_LINE) != 1:
        raise RuntimeError(
            "flagship pymediate source no longer matches the release-runner contract"
        )
    pyproject.write_text(text.replace(FLAGSHIP_PYMEDIATE_SOURCE_LINE, ""))


def run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    print(f"  $ {' '.join(cmd)}", flush=True)
    # Drop any inherited VIRTUAL_ENV (e.g. the repo's own .venv when run via poe) so uv
    # targets the example workspace's environment, not the caller's.
    env = {key: value for key, value in os.environ.items() if key != "VIRTUAL_ENV"}
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, env=env)


def run_example(
    example: Path,
    workdir: Path,
    version: str | None,
    index_url: str,
    wheel: Path | None,
) -> Result:
    name = example.name
    print(f"\n=== {name} ===", flush=True)

    violation = check_contract(example / "pyproject.toml")
    if violation:
        return Result(name, ok=False, detail=f"contract violation: {violation}")

    workspace = workdir / name
    # Exclude transient local state: a copied .venv has broken interpreter symlinks, and a
    # fresh sync in the workspace recreates it anyway.
    copy_example_for_release(example, workspace)

    if wheel is not None:
        # Wheel mode: `uv add <path>` re-pins pymediate to the local wheel via a path
        # source — no index involvement at all.
        pin_cmd = ["uv", "add", str(wheel.resolve())]
    else:
        pin_cmd = [
            "uv",
            "add",
            "--index",
            f"{STAGING_INDEX_NAME}={index_url}",
            f"pymediate=={version}",
        ]

    steps = [
        pin_cmd,
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
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--version", help="Exact published pymediate version to test, e.g. 0.2.0")
    target.add_argument(
        "--wheel",
        type=Path,
        help="Path to a locally built pymediate wheel to test instead of an index",
    )
    parser.add_argument(
        "--index",
        default="https://test.pypi.org/simple/",
        help="Simple-API index URL hosting --version (default: TestPyPI); ignored with --wheel",
    )
    args = parser.parse_args()

    if args.wheel is not None and not args.wheel.is_file():
        print(f"Wheel not found: {args.wheel}", file=sys.stderr)
        return 2

    examples = discover_examples()
    if not examples:
        print("No examples/*/pyproject.toml found — nothing to run.")
        return 0

    with tempfile.TemporaryDirectory(prefix="pymediate-examples-") as tmp:
        results = [
            run_example(path, Path(tmp), args.version, args.index, args.wheel) for path in examples
        ]

    target_desc = (
        f"wheel {args.wheel.name}" if args.wheel else f"pymediate=={args.version} ({args.index})"
    )
    width = max(len(result.example) for result in results)
    print(f"\nExamples against {target_desc}:")
    for result in results:
        status = "PASS" if result.ok else "FAIL"
        suffix = f"  ({result.detail})" if result.detail else ""
        print(f"  {result.example:<{width}}  {status}{suffix}")

    return 0 if all(result.ok for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
