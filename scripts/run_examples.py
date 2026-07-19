#!/usr/bin/env python3
"""Validate examples or run them against a specific pymediate build.

Four targets cover local checks and release verification (see OPERATIONS.md and
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

  --check-contract  Validate every discovered project without installing or running it.

  --check-repository
                    Validate repository-only structure such as names, README sections,
                    editor settings, devcontainers, workspace entries, and relative links.

Wheel and version runs copy each examples/<name>/ project to a temporary directory (the
checkout is never modified), re-pin it to the build under test, and run its tests via
`uv run pytest`. The command exits non-zero if any contract check or example fails. It is
also usable locally, for example:

    python3 scripts/run_examples.py --check-contract
    python3 scripts/run_examples.py --check-repository
    python3 scripts/run_examples.py --version 0.1.5 --index https://pypi.org/simple/
    uv build && python3 scripts/run_examples.py --wheel dist/pymediate-*.whl
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlsplit

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLES_DIR = REPO_ROOT / "examples"
STAGING_INDEX_NAME = "release-staging"
# The `name = "..."` line `uv add --index` writes for the staging index. The runner inserts
# `explicit = true` right after it — anchoring on the unique name line (rather than the whole
# block) keeps this independent of uv's field order. See make_staging_index_explicit.
STAGING_INDEX_NAME_LINE = re.compile(rf'(?m)^(name = "{STAGING_INDEX_NAME}"\n)')
FLAGSHIP_EXAMPLE = "900-hexagonal-architecture"
# Every example depends on the in-branch pymediate source by default, so `uv sync` in a
# checkout runs against this source tree. The release runner strips this exact line from its
# temp copy (copy_example_for_release) and re-pins to the wheel or published version under test.
PYMEDIATE_SOURCE = {"path": "../..", "editable": True}
PYMEDIATE_SOURCE_LINE = 'pymediate = { path = "../..", editable = true }\n'
PYMEDIATE_REQUIREMENT = re.compile(r"pymediate(?:\[[A-Za-z0-9_,.-]+\])?>=\d+(?:\.\d+){1,2}")
EXAMPLE_DIRECTORY = re.compile(r"\d{3}-[a-z0-9]+(?:-[a-z0-9]+)*")
MARKDOWN_LINK = re.compile(r"!?\[[^]]*\]\(([^)]+)\)")
ORDINARY_EDITOR_TEMPLATE = "010-basic"
TYPE_CHECKER_EXTENSIONS = {"ms-python.vscode-pylance", "detachhead.basedpyright"}
EDITOR_EXCLUDE_STEMS = {
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "build",
    "dist",
    "htmlcov",
    "site",
}
ORDINARY_EDITOR_EXCLUDE_STEMS = EDITOR_EXCLUDE_STEMS | {".mypy_cache"}


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
    example = pyproject.parent
    missing = [name for name in ("README.md", "uv.lock") if not (example / name).is_file()]
    if missing:
        return f"is missing required file(s): {', '.join(missing)}"

    text = pyproject.read_text()
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        return f"has invalid pyproject.toml: {error}"

    tool = data.get("tool", {})
    uv = tool.get("uv", {}) if isinstance(tool, dict) else {}
    if isinstance(uv, dict) and "index" in uv:
        return (
            "defines a tool.uv.index; the examples contract reserves indexes for this runner "
            "(see examples/README.md)"
        )

    project = data.get("project", {})
    dependencies = project.get("dependencies", []) if isinstance(project, dict) else []
    pymediate_dependencies = [
        dependency
        for dependency in dependencies
        if isinstance(dependency, str) and dependency.startswith("pymediate")
    ]
    if len(pymediate_dependencies) != 1:
        return "must declare exactly one direct pymediate dependency in [project].dependencies"
    requirement = pymediate_dependencies[0].replace(" ", "")
    if PYMEDIATE_REQUIREMENT.fullmatch(requirement) is None:
        return (
            "must declare pymediate with only a loose lower bound, for example "
            "pymediate>=0.6.0 or pymediate[di]>=0.6.0"
        )

    dependency_groups = data.get("dependency-groups", {})
    dev_dependencies = (
        dependency_groups.get("dev", []) if isinstance(dependency_groups, dict) else []
    )
    if not any(
        isinstance(dependency, str)
        and (dependency == "pytest" or dependency.startswith(("pytest>", "pytest=")))
        for dependency in dev_dependencies
    ):
        return "must include pytest in the default dev dependency group"

    sources = uv.get("sources", {}) if isinstance(uv, dict) else {}
    if not isinstance(sources, dict):
        return "has an invalid [tool.uv.sources] table"
    if sources.get("pymediate") != PYMEDIATE_SOURCE or text.count(PYMEDIATE_SOURCE_LINE) != 1:
        return (
            "must declare the in-branch pymediate source exactly once as "
            f"`{PYMEDIATE_SOURCE_LINE.strip()}`; the release runner strips it per example"
        )
    invalid_sources = {
        name: source
        for name, source in sources.items()
        if name != "pymediate" and source != {"workspace": True}
    }
    if invalid_sources:
        return (
            "defines a disallowed [tool.uv.sources] entry; only the in-branch pymediate "
            "source and internal { workspace = true } sources are allowed"
        )
    return None


def _markdown_targets(readme: Path) -> list[str]:
    """Return Markdown link and image targets outside fenced code blocks."""
    targets: list[str] = []
    in_fence = False
    for line in readme.read_text().splitlines():
        if line.lstrip().startswith(("```", "~~~")):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        for match in MARKDOWN_LINK.finditer(line):
            value = match.group(1).strip()
            if value.startswith("<") and ">" in value:
                value = value[1 : value.index(">")]
            else:
                value = value.split(maxsplit=1)[0]
            targets.append(value)
    return targets


def _second_level_headings(markdown: str) -> list[tuple[str, int]]:
    """Return exact level-two headings and offsets outside fenced code blocks."""
    headings: list[tuple[str, int]] = []
    in_fence = False
    offset = 0
    for line in markdown.splitlines(keepends=True):
        stripped = line.lstrip()
        if stripped.startswith(("```", "~~~")):
            in_fence = not in_fence
        elif not in_fence and stripped.startswith("## ") and not stripped.startswith("### "):
            headings.append((stripped.strip(), offset + len(line) - len(stripped)))
        offset += len(line)
    return headings


def check_repository_quality(examples: list[Path]) -> dict[str, list[str]]:
    """Return repository-only example quality violations grouped by project."""
    violations: defaultdict[str, list[str]] = defaultdict(list)

    def report(project: str, message: str) -> None:
        violations[project].append(message)

    def check_links(project: str, readme: Path) -> None:
        try:
            targets = _markdown_targets(readme)
        except OSError as error:
            report(project, f"cannot read {readme.relative_to(REPO_ROOT)}: {error}")
            return
        for target in targets:
            try:
                parsed = urlsplit(target)
            except ValueError:
                report(project, f"{readme.relative_to(REPO_ROOT)} has an invalid link: {target}")
                continue
            if parsed.scheme or parsed.netloc or target.startswith(("#", "/")):
                continue
            relative_target = unquote(parsed.path)
            if relative_target and not (readme.parent / relative_target).exists():
                display = readme.relative_to(REPO_ROOT)
                report(project, f"{display} has a broken relative link: {target}")

    names = {example.name for example in examples}
    sorted_names = sorted(names)

    gallery = EXAMPLES_DIR / "README.md"
    try:
        gallery_text = gallery.read_text()
    except OSError as error:
        report("repository", f"cannot read examples/README.md: {error}")
        gallery_text = ""
    check_links("repository", gallery)

    for name in sorted_names:
        if EXAMPLE_DIRECTORY.fullmatch(name) is None:
            report(name, "directory name must use NNN-kebab-case")
        if name.endswith("-sync") and name.removesuffix("-sync") not in names:
            report(name, "synchronous example has no matching asynchronous project")
        if f"({name}/)" not in gallery_text:
            report(name, "examples/README.md has no gallery link for this project")

    names_by_position: defaultdict[str, list[str]] = defaultdict(list)
    for name in names:
        names_by_position[name[:3]].append(name)
    for position, positioned_names in names_by_position.items():
        if len(positioned_names) <= 1:
            continue
        bases = {name.removesuffix("-sync") for name in positioned_names}
        if len(positioned_names) != 2 or len(bases) != 1:
            report("repository", f"position {position} is used by unrelated projects")

    try:
        workspace = json.loads((REPO_ROOT / "pymediate.code-workspace").read_text())
        workspace_examples = [
            folder.get("path")
            for folder in workspace.get("folders", [])
            if isinstance(folder, dict) and str(folder.get("path", "")).startswith("examples/")
        ]
    except (OSError, json.JSONDecodeError, AttributeError) as error:
        report("repository", f"cannot read pymediate.code-workspace: {error}")
        workspace_examples = []
    expected_workspace_examples = [f"examples/{name}" for name in sorted_names]
    if workspace_examples != expected_workspace_examples:
        report("repository", "pymediate.code-workspace must list every example in numeric order")

    devcontainer_names = {
        path.parent.name for path in (REPO_ROOT / ".devcontainer").glob("*/devcontainer.json")
    }
    missing_devcontainers = sorted(names - devcontainer_names)
    extra_devcontainers = sorted(devcontainer_names - names)
    if missing_devcontainers:
        report("repository", f"missing devcontainers: {', '.join(missing_devcontainers)}")
    if extra_devcontainers:
        report("repository", f"devcontainers without examples: {', '.join(extra_devcontainers)}")

    template_dir = EXAMPLES_DIR / ORDINARY_EDITOR_TEMPLATE
    try:
        editor_templates = {
            relative: json.loads((template_dir / relative).read_text())
            for relative in (
                Path(".vscode/settings.json"),
                Path(".vscode/extensions.json"),
                Path("pyrightconfig.json"),
            )
        }
    except (OSError, json.JSONDecodeError) as error:
        report("repository", f"cannot read ordinary editor template: {error}")
        editor_templates = {}

    for example in examples:
        name = example.name
        readme = example / "README.md"
        try:
            readme_text = readme.read_text()
        except OSError as error:
            report(name, f"cannot read README.md: {error}")
            readme_text = ""

        if not readme_text.startswith(f"# {name}\n"):
            report(name, "README title must match the directory name")
        badge_path = f".devcontainer%2F{name}%2Fdevcontainer.json"
        if badge_path not in readme_text:
            report(name, "README Codespaces badge does not target its devcontainer")

        headings = _second_level_headings(readme_text)
        heading_positions = {
            heading: next(
                (position for found_heading, position in headings if found_heading == heading), -1
            )
            for heading in ("## Run", "## Read the code", "## Details", "## Where next")
        }
        required_headings = ("## Run", "## Read the code", "## Where next")
        for heading in required_headings:
            if heading_positions[heading] < 0:
                report(name, f"README is missing {heading}")
        if all(heading_positions[heading] >= 0 for heading in required_headings):
            if not (
                heading_positions["## Run"]
                < heading_positions["## Read the code"]
                < heading_positions["## Where next"]
            ):
                report(name, "README sections must order Run, Read the code, then Where next")
        if heading_positions["## Details"] >= 0 and not (
            heading_positions["## Read the code"]
            < heading_positions["## Details"]
            < heading_positions["## Where next"]
        ):
            report(name, "README Details must follow Read the code and precede Where next")
        if heading_positions["## Run"] >= 0:
            next_heading = min(
                (position for _, position in headings if position > heading_positions["## Run"]),
                default=-1,
            )
            run_section = readme_text[
                heading_positions["## Run"] : next_heading if next_heading >= 0 else None
            ]
            if re.search(r"(?m)^cd examples/", run_section):
                report(name, "README Run commands must start from the example directory")
        if (
            heading_positions["## Read the code"] >= 0
            and "| File | What to read |" not in readme_text
        ):
            report(name, "README Read the code section must use a File | What to read table")

        for nested_readme in example.rglob("README.md"):
            relative_parts = nested_readme.relative_to(example).parts
            if any(
                part.startswith(".") or part in {"build", "dist", "node_modules", "site"}
                for part in relative_parts[:-1]
            ):
                continue
            check_links(name, nested_readme)

        try:
            pyproject_data = tomllib.loads((example / "pyproject.toml").read_text())
        except (OSError, tomllib.TOMLDecodeError) as error:
            report(name, f"cannot read pyproject.toml: {error}")
            pyproject_data = {}
        project = pyproject_data.get("project", {})
        project_name = project.get("name") if isinstance(project, dict) else None
        if project_name != f"pymediate-example-{name}":
            report(name, f"[project].name must be pymediate-example-{name}")
        tool = pyproject_data.get("tool", {})
        ruff = tool.get("ruff", {}) if isinstance(tool, dict) else {}
        ruff_lint = ruff.get("lint", {}) if isinstance(ruff, dict) else {}
        ruff_format = ruff.get("format", {}) if isinstance(ruff, dict) else {}
        if not (
            isinstance(ruff, dict)
            and ruff.get("line-length") == 100
            and isinstance(ruff_lint, dict)
            and ruff_lint.get("select") == ["E", "W", "F", "I", "B", "C4", "UP"]
            and isinstance(ruff_format, dict)
            and ruff_format.get("quote-style") == "double"
        ):
            report(name, "pyproject.toml does not contain the shared Ruff settings")

        editor_data: dict[Path, object] = {}
        for relative in (
            Path(".vscode/settings.json"),
            Path(".vscode/extensions.json"),
            Path("pyrightconfig.json"),
        ):
            try:
                editor_data[relative] = json.loads((example / relative).read_text())
            except (OSError, json.JSONDecodeError) as error:
                report(name, f"cannot read {relative}: {error}")

        settings = editor_data.get(Path(".vscode/settings.json"), {})
        extensions = editor_data.get(Path(".vscode/extensions.json"), {})
        pyright = editor_data.get(Path("pyrightconfig.json"), {})
        recommendations = (
            extensions.get("recommendations", []) if isinstance(extensions, dict) else []
        )
        python_editor = settings.get("[python]", {}) if isinstance(settings, dict) else {}
        code_actions = (
            python_editor.get("editor.codeActionsOnSave", {})
            if isinstance(python_editor, dict)
            else {}
        )
        if not (
            isinstance(settings, dict)
            and settings.get("python.defaultInterpreterPath")
            == "${workspaceFolder}/.venv/bin/python"
        ):
            report(name, "editor interpreter must point to the example .venv")
        if not (
            isinstance(settings, dict)
            and isinstance(python_editor, dict)
            and isinstance(code_actions, dict)
            and python_editor.get("editor.defaultFormatter") == "charliermarsh.ruff"
            and python_editor.get("editor.formatOnSave") is True
            and code_actions.get("source.fixAll") == "explicit"
            and code_actions.get("source.organizeImports") == "explicit"
            and settings.get("ruff.enable") is True
            and settings.get("python.testing.pytestEnabled") is True
            and settings.get("python.testing.unittestEnabled") is False
            and settings.get("python.testing.autoTestDiscoverOnSaveEnabled") is False
        ):
            report(name, "editor settings must enable the shared Ruff and pytest configuration")
        exclude_stems = (
            EDITOR_EXCLUDE_STEMS if name == FLAGSHIP_EXAMPLE else ORDINARY_EDITOR_EXCLUDE_STEMS
        )
        if isinstance(settings, dict):
            watcher_excludes = settings.get("files.watcherExclude", {})
            search_excludes = settings.get("search.exclude", {})
            file_excludes = settings.get("files.exclude", {})
        else:
            watcher_excludes = search_excludes = file_excludes = {}
        if not (
            isinstance(watcher_excludes, dict)
            and isinstance(search_excludes, dict)
            and isinstance(file_excludes, dict)
            and all(watcher_excludes.get(f"**/{stem}/**") is True for stem in exclude_stems)
            and all(search_excludes.get(f"**/{stem}/**") is True for stem in exclude_stems)
            and all(file_excludes.get(f"**/{stem}") is True for stem in exclude_stems)
        ):
            report(name, "editor settings must exclude shared environment and cache paths")
        if (
            name != FLAGSHIP_EXAMPLE
            and isinstance(settings, dict)
            and settings.get("python.analysis.diagnosticMode") != "openFilesOnly"
        ):
            report(name, "ordinary examples must use open-files-only editor diagnostics")
        if not (
            isinstance(pyright, dict)
            and pyright.get("typeCheckingMode") == "standard"
            and pyright.get("venvPath") == "."
            and pyright.get("venv") == ".venv"
        ):
            report(name, "pyrightconfig.json does not select the example .venv in standard mode")
        pyright_excludes = pyright.get("exclude", []) if isinstance(pyright, dict) else []
        if not (
            isinstance(pyright_excludes, list)
            and all(f"**/{stem}" in pyright_excludes for stem in exclude_stems)
        ):
            report(name, "pyrightconfig.json must exclude shared environment and cache paths")
        if not (
            isinstance(recommendations, list)
            and "ms-python.python" in recommendations
            and "charliermarsh.ruff" in recommendations
            and TYPE_CHECKER_EXTENSIONS.intersection(recommendations)
        ):
            report(name, "editor recommendations must include Python, a type checker, and Ruff")

        if name != FLAGSHIP_EXAMPLE and editor_templates:
            for relative, expected in editor_templates.items():
                if editor_data.get(relative) != expected:
                    report(name, f"{relative} differs from the ordinary example template")

        devcontainer_path = REPO_ROOT / ".devcontainer" / name / "devcontainer.json"
        try:
            devcontainer = json.loads(devcontainer_path.read_text())
        except (OSError, json.JSONDecodeError) as error:
            report(name, f"cannot read devcontainer.json: {error}")
            continue
        if not isinstance(devcontainer, dict):
            report(name, "devcontainer.json must contain an object")
            continue
        if devcontainer.get("name") != f"pymediate example: {name}":
            report(name, "devcontainer name must match the example directory")
        features = devcontainer.get("features", {})
        if not (
            isinstance(features, dict)
            and "ghcr.io/jsburckhardt/devcontainer-features/uv:1" in features
        ):
            report(name, "devcontainer must install the uv feature")
        if name == FLAGSHIP_EXAMPLE:
            build = devcontainer.get("build", {})
            build_args = build.get("args", {}) if isinstance(build, dict) else {}
            if not (
                isinstance(build, dict)
                and build.get("dockerfile") == "Dockerfile"
                and build.get("context") == "."
                and isinstance(build_args, dict)
                and build_args.get("PYTHON_VERSION") == "3.12"
            ):
                report(name, "flagship devcontainer must build its Dockerfile with Python 3.12")
        elif devcontainer.get("image") != "mcr.microsoft.com/devcontainers/python:3.12":
            report(name, "ordinary devcontainers must use the Python 3.12 image")
        expected_workspace = f"/workspaces/${{localWorkspaceFolderBasename}}/examples/{name}"
        if devcontainer.get("workspaceFolder") != expected_workspace:
            report(name, "devcontainer workspaceFolder must open the example directory")
        if devcontainer.get("postCreateCommand") != "uv sync":
            report(name, "devcontainer postCreateCommand must be uv sync")
        customizations = devcontainer.get("customizations", {})
        vscode = customizations.get("vscode", {}) if isinstance(customizations, dict) else {}
        if not isinstance(vscode, dict):
            vscode = {}
        devcontainer_settings = vscode.get("settings", {})
        if not isinstance(devcontainer_settings, dict):
            devcontainer_settings = {}
        if vscode.get("extensions") != recommendations:
            report(name, "devcontainer extensions must match .vscode/extensions.json")
        if devcontainer_settings.get("python.defaultInterpreterPath") != (
            "${containerWorkspaceFolder}/.venv/bin/python"
        ):
            report(name, "devcontainer interpreter must use the opened example workspace")

    return dict(violations)


def copy_example_for_release(example: Path, workspace: Path) -> None:
    """Copy one example and remove its checkout-only in-branch pymediate source.

    Every example depends on the source tree via ``[tool.uv.sources]`` for local development;
    stripping that line lets the runner re-pin the copy to the wheel or published version under
    test, so releases are verified against the built package rather than the checkout.
    """
    shutil.copytree(
        example,
        workspace,
        ignore=shutil.ignore_patterns(".venv", "__pycache__", ".pytest_cache"),
    )
    pyproject = workspace / "pyproject.toml"
    text = pyproject.read_text()
    if text.count(PYMEDIATE_SOURCE_LINE) != 1:
        raise RuntimeError("example pymediate source no longer matches the release-runner contract")
    pyproject.write_text(text.replace(PYMEDIATE_SOURCE_LINE, ""))


def run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    print(f"  $ {' '.join(cmd)}", flush=True)
    # Drop any inherited VIRTUAL_ENV (e.g. the repo's own .venv when run via poe) so uv
    # targets the example workspace's environment, not the caller's.
    env = {key: value for key, value in os.environ.items() if key != "VIRTUAL_ENV"}
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, env=env)


def pymediate_extras(pyproject: Path) -> str:
    """Return the example's pymediate extras suffix, e.g. ``[di]`` (empty string if none)."""
    data = tomllib.loads(pyproject.read_text())
    project = data.get("project", {})
    dependencies = project.get("dependencies", []) if isinstance(project, dict) else []
    for dependency in dependencies:
        if isinstance(dependency, str) and dependency.replace(" ", "").startswith("pymediate"):
            match = re.match(r"pymediate(\[[A-Za-z0-9_,.-]+\])?", dependency.replace(" ", ""))
            if match:
                return match.group(1) or ""
    return ""


def make_staging_index_explicit(pyproject: Path) -> None:
    """Mark the runner's staging index ``explicit`` so only pymediate resolves from it.

    ``uv add --index`` writes a general index, which uv's first-index strategy then prefers
    for *every* dependency — pulling stale placeholders (pytest, click, jsonschema, …) off
    TestPyPI and making resolution unsatisfiable (issue #126). An explicit index is consulted
    only for packages that name it in ``[tool.uv.sources]``, i.e. pymediate alone.
    """
    text = pyproject.read_text()
    patched, count = STAGING_INDEX_NAME_LINE.subn(lambda m: m.group(1) + "explicit = true\n", text)
    if count != 1:
        raise RuntimeError(f"could not mark the {STAGING_INDEX_NAME} index explicit")
    pyproject.write_text(patched)


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
        # Version mode: pin pymediate to the release candidate on the staging index while
        # every other dependency keeps resolving from real PyPI. `--frozen` writes the pin
        # (extras preserved) and the staging-index source without resolving; the follow-up
        # make_staging_index_explicit call then marks that index `explicit` so only pymediate
        # is ever fetched from it (see that helper and issue #126).
        pin_cmd = [
            "uv",
            "add",
            "--frozen",
            "--index",
            f"{STAGING_INDEX_NAME}={index_url}",
            f"pymediate{pymediate_extras(example / 'pyproject.toml')}=={version}",
        ]

    proc = run(pin_cmd, cwd=workspace)
    sys.stdout.write(proc.stdout)
    sys.stderr.write(proc.stderr)
    if proc.returncode != 0:
        return Result(name, ok=False, detail=f"`{' '.join(pin_cmd)}` exited {proc.returncode}")

    if wheel is None:
        try:
            make_staging_index_explicit(workspace / "pyproject.toml")
        except RuntimeError as error:
            return Result(name, ok=False, detail=str(error))

    for cmd in (["uv", "sync"], ["uv", "run", "pytest"]):
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
    target.add_argument(
        "--check-contract",
        action="store_true",
        help="Validate every example's release contract without installing dependencies",
    )
    target.add_argument(
        "--check-repository",
        action="store_true",
        help="Validate example names, documentation, editor files, and repository wiring",
    )
    parser.add_argument(
        "--index",
        default="https://test.pypi.org/simple/",
        help="Simple-API index URL hosting --version (default: TestPyPI)",
    )
    args = parser.parse_args()

    if args.wheel is not None and not args.wheel.is_file():
        print(f"Wheel not found: {args.wheel}", file=sys.stderr)
        return 2

    examples = discover_examples()
    if not examples:
        print("No examples/*/pyproject.toml found.", file=sys.stderr)
        return 1

    violations = {
        example.name: violation
        for example in examples
        if (violation := check_contract(example / "pyproject.toml")) is not None
    }
    if violations:
        print("Examples contract violations:", file=sys.stderr)
        for name, violation in violations.items():
            print(f"  {name}: {violation}", file=sys.stderr)
        return 1

    if args.check_contract:
        print(f"Examples contract: PASS ({len(examples)} projects)")
        return 0

    if args.check_repository:
        quality_violations = check_repository_quality(examples)
        if quality_violations:
            print("Examples repository-quality violations:", file=sys.stderr)
            for name, messages in quality_violations.items():
                for message in messages:
                    print(f"  {name}: {message}", file=sys.stderr)
            return 1
        print(f"Examples repository quality: PASS ({len(examples)} projects)")
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
