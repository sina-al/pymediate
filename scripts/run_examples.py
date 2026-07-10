#!/usr/bin/env python3
"""Run every example's tests against a specific pymediate build.

Two modes, one per stage of the release flow (see OPERATIONS.md and examples/README.md):

  --wheel PATH      Test against a locally built wheel. Used by the release PR's required
                    "Examples" check (release-pr-report.yml): breaking changes that stale
                    examples can't absorb fail *before* merge — no tag, no burned version.

  --version X.Y.Z   Test against a published release on an index (default TestPyPI). Used
    [--index URL]   by release.yml after the TestPyPI publish to validate the real
                    publish-and-install path. Only pymediate resolves from the staging
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

INDEX_TEMPLATE = """
# Appended by scripts/run_examples.py (release pipeline): resolve pymediate — and only
# pymediate — from the staging index; everything else keeps coming from real PyPI.
[[tool.uv.index]]
name = "{name}"
url = "{url}"
explicit = true
"""

SOURCE_LINE = 'pymediate = {{ index = "{name}" }}\n'


def pin_to_index(pyproject: Path, name: str, url: str) -> None:
    """Point pymediate — and only pymediate — at a staging index.

    Appends an ``explicit = true`` index and a ``[tool.uv.sources]`` entry for pymediate.
    Workspace examples already have a ``[tool.uv.sources]`` table (their member-to-member
    dependencies live there), so the entry is merged into it rather than appended as a
    duplicate table, which TOML forbids.
    """
    text = pyproject.read_text()
    source_line = SOURCE_LINE.format(name=name)
    if "[tool.uv.sources]" in text:
        text = text.replace("[tool.uv.sources]\n", "[tool.uv.sources]\n" + source_line, 1)
        text += INDEX_TEMPLATE.format(name=name, url=url)
    else:
        text += INDEX_TEMPLATE.format(name=name, url=url) + "\n[tool.uv.sources]\n" + source_line
    pyproject.write_text(text)


@dataclass
class Result:
    example: str
    ok: bool
    detail: str = ""


def discover_examples() -> list[Path]:
    if not EXAMPLES_DIR.is_dir():
        return []
    return sorted(path.parent for path in EXAMPLES_DIR.glob("*/pyproject.toml") if path.is_file())


def check_contract(example: Path) -> str | None:
    """Return a contract-violation message, or None if the example is runnable.

    Every pyproject.toml in the example (the root and, for uv-workspace examples, each
    member) is checked: indexes are always reserved for this runner, and the only
    ``[tool.uv.sources]`` entries an example may define itself are workspace members —
    anything else (a path, a git URL, an index) would fight the release re-pin.
    """
    for pyproject in sorted(example.rglob("pyproject.toml")):
        if ".venv" in pyproject.parts:
            continue
        data = tomllib.loads(pyproject.read_text())
        uv_table = data.get("tool", {}).get("uv", {})
        relative = pyproject.relative_to(example)
        if uv_table.get("index"):
            return (
                f"{relative} defines [[tool.uv.index]]; the examples contract reserves "
                "indexes for this runner (see examples/README.md)"
            )
        for source_name, source in uv_table.get("sources", {}).items():
            if source != {"workspace": True}:
                return (
                    f"{relative} defines a non-workspace [tool.uv.sources] entry for "
                    f"{source_name!r}; the examples contract only allows "
                    "`{ workspace = true }` sources (see examples/README.md)"
                )
    root_text = (example / "pyproject.toml").read_text()
    if "pymediate" not in root_text and not any(
        "pymediate" in path.read_text()
        for path in example.rglob("pyproject.toml")
        if ".venv" not in path.parts
    ):
        return "does not depend on pymediate"
    return None


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

    violation = check_contract(example)
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

    if wheel is not None:
        # Wheel mode: `uv add <path>` re-pins pymediate to the local wheel via a path
        # source — no index involvement at all (uv merges the source entry itself).
        pin_cmd = ["uv", "add", str(wheel.resolve())]
    else:
        pin_to_index(workspace / "pyproject.toml", STAGING_INDEX_NAME, index_url)
        pin_cmd = ["uv", "add", f"pymediate=={version}"]

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
