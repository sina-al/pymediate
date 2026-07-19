"""Tests for example contract, repository quality, and release-copy preparation."""

import json
from pathlib import Path

from pytest import MonkeyPatch

from scripts import run_examples
from scripts.run_examples import (
    FLAGSHIP_EXAMPLE,
    PYMEDIATE_SOURCE_LINE,
    check_contract,
    check_repository_quality,
    copy_example_for_release,
    discover_examples,
)


def _write_example(
    tmp_path: Path,
    name: str,
    source_line: str = PYMEDIATE_SOURCE_LINE,
    *,
    requirement: str = "pymediate>=0.5.0",
    dev_dependencies: str = 'dev = ["pytest>=8.0.0"]',
) -> Path:
    example = tmp_path / name
    example.mkdir(parents=True)
    (example / "pyproject.toml").write_text(
        "[project]\n"
        f'name = "{name}"\n'
        'version = "0.1.0"\n'
        f'dependencies = ["{requirement}"]\n'
        "\n[dependency-groups]\n"
        f"{dev_dependencies}\n" + (f"\n[tool.uv.sources]\n{source_line}" if source_line else "")
    )
    (example / "README.md").write_text(f"# {name}\n")
    (example / "uv.lock").write_text("version = 1\n")
    return example


def _write_quality_repository(tmp_path: Path, monkeypatch: MonkeyPatch) -> Path:
    """Create one mechanically valid example repository for focused quality tests."""
    example = tmp_path / "examples" / "010-basic"
    example.mkdir(parents=True)
    (example / ".vscode").mkdir()
    (tmp_path / ".devcontainer" / example.name).mkdir(parents=True)

    (example / "README.md").write_text(
        f"# {example.name}\n\n"
        "[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)]"
        "(https://codespaces.new/sina-al/pymediate?"
        f"devcontainer_path=.devcontainer%2F{example.name}%2Fdevcontainer.json)\n\n"
        "## Run\n\n```bash\nuv sync\nuv run pytest\n```\n\n"
        "## Read the code\n\n| File | What to read |\n| --- | --- |\n"
        "| [`app.py`](app.py) | Start here. |\n\n"
        "## Where next\n\nReturn to the gallery.\n"
    )
    (example / "app.py").write_text("")
    (example / "pyproject.toml").write_text(
        "[project]\n"
        f'name = "pymediate-example-{example.name}"\n'
        'version = "0.1.0"\n'
        'dependencies = ["pymediate>=0.5.0"]\n\n'
        "[tool.ruff]\n"
        "line-length = 100\n\n"
        "[tool.ruff.lint]\n"
        'select = ["E", "W", "F", "I", "B", "C4", "UP"]\n\n'
        "[tool.ruff.format]\n"
        'quote-style = "double"\n'
    )
    exclude_stems = [
        ".venv",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "build",
        "dist",
        "htmlcov",
        "site",
    ]
    (example / ".vscode" / "settings.json").write_text(
        json.dumps(
            {
                "[python]": {
                    "editor.defaultFormatter": "charliermarsh.ruff",
                    "editor.formatOnSave": True,
                    "editor.codeActionsOnSave": {
                        "source.fixAll": "explicit",
                        "source.organizeImports": "explicit",
                    },
                },
                "ruff.enable": True,
                "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
                "python.testing.pytestEnabled": True,
                "python.testing.unittestEnabled": False,
                "python.testing.autoTestDiscoverOnSaveEnabled": False,
                "files.watcherExclude": {f"**/{stem}/**": True for stem in exclude_stems},
                "search.exclude": {f"**/{stem}/**": True for stem in exclude_stems},
                "files.exclude": {f"**/{stem}": True for stem in exclude_stems},
                "python.analysis.diagnosticMode": "openFilesOnly",
            }
        )
    )
    recommendations = ["ms-python.python", "detachhead.basedpyright", "charliermarsh.ruff"]
    (example / ".vscode" / "extensions.json").write_text(
        '{"recommendations": ["ms-python.python", "detachhead.basedpyright", '
        '"charliermarsh.ruff"]}\n'
    )
    (example / "pyrightconfig.json").write_text(
        json.dumps(
            {
                "typeCheckingMode": "standard",
                "venvPath": ".",
                "venv": ".venv",
                "exclude": [f"**/{stem}" for stem in exclude_stems],
            }
        )
    )
    (tmp_path / ".devcontainer" / example.name / "devcontainer.json").write_text(
        json.dumps(
            {
                "name": f"pymediate example: {example.name}",
                "image": "mcr.microsoft.com/devcontainers/python:3.12",
                "features": {"ghcr.io/jsburckhardt/devcontainer-features/uv:1": {}},
                "workspaceFolder": (
                    f"/workspaces/${{localWorkspaceFolderBasename}}/examples/{example.name}"
                ),
                "postCreateCommand": "uv sync",
                "customizations": {
                    "vscode": {
                        "settings": {
                            "python.defaultInterpreterPath": (
                                "${containerWorkspaceFolder}/.venv/bin/python"
                            )
                        },
                        "extensions": recommendations,
                    }
                },
            }
        )
    )
    (tmp_path / "examples" / "README.md").write_text(
        f"# Examples\n\n[{example.name}]({example.name}/)\n"
    )
    (tmp_path / "pymediate.code-workspace").write_text(
        '{"folders": [{"path": "examples/010-basic"}]}\n'
    )

    monkeypatch.setattr(run_examples, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(run_examples, "EXAMPLES_DIR", tmp_path / "examples")
    return example


def test_contract_requires_the_in_branch_pymediate_source(tmp_path: Path) -> None:
    # Arrange
    valid = _write_example(tmp_path / "valid", "010-basic", PYMEDIATE_SOURCE_LINE)
    wrong_source = _write_example(
        tmp_path / "wrong-source",
        "010-basic",
        'pymediate = { path = "../source", editable = true }\n',
    )
    missing_source = _write_example(tmp_path / "missing", "010-basic", "")

    # Act
    valid_violation = check_contract(valid / "pyproject.toml")
    wrong_violation = check_contract(wrong_source / "pyproject.toml")
    missing_violation = check_contract(missing_source / "pyproject.toml")

    # Assert
    assert valid_violation is None
    assert wrong_violation is not None
    assert "in-branch pymediate source" in wrong_violation
    assert missing_violation is not None
    assert "in-branch pymediate source" in missing_violation


def test_contract_requires_release_files_dependency_and_pytest(tmp_path: Path) -> None:
    # Arrange
    missing_files = _write_example(tmp_path, "missing-files")
    (missing_files / "README.md").unlink()
    bare_dependency = _write_example(tmp_path, "bare-dependency", requirement="pymediate")
    bounded_dependency = _write_example(
        tmp_path, "bounded-dependency", requirement="pymediate>=0.5.0,<0.7"
    )
    missing_pytest = _write_example(
        tmp_path,
        "missing-pytest",
        dev_dependencies='dev = ["ruff>=0.12.0"]',
    )

    # Act
    missing_files_violation = check_contract(missing_files / "pyproject.toml")
    bare_dependency_violation = check_contract(bare_dependency / "pyproject.toml")
    bounded_dependency_violation = check_contract(bounded_dependency / "pyproject.toml")
    missing_pytest_violation = check_contract(missing_pytest / "pyproject.toml")

    # Assert
    assert missing_files_violation is not None
    assert "README.md" in missing_files_violation
    assert bare_dependency_violation is not None
    assert "loose lower bound" in bare_dependency_violation
    assert bounded_dependency_violation is not None
    assert "loose lower bound" in bounded_dependency_violation
    assert missing_pytest_violation is not None
    assert "pytest" in missing_pytest_violation


def test_contract_allows_internal_workspace_sources(tmp_path: Path) -> None:
    # Arrange
    example = _write_example(
        tmp_path,
        "workspace-example",
        PYMEDIATE_SOURCE_LINE + "internal-package = { workspace = true }\n",
    )

    # Act
    violation = check_contract(example / "pyproject.toml")

    # Assert
    assert violation is None


def test_contract_checks_parsed_index_tables_not_comments_or_strings(tmp_path: Path) -> None:
    # Arrange
    mentioned = _write_example(tmp_path, "mentioned-index")
    mentioned_pyproject = mentioned / "pyproject.toml"
    mentioned_pyproject.write_text(
        mentioned_pyproject.read_text().replace(
            'version = "0.1.0"\n',
            'version = "0.1.0"\ndescription = "Mentions [tool.uv.index] in prose"\n',
        )
        + "\n# [tool.uv.index] is reserved for the runner.\n"
    )
    configured = _write_example(tmp_path, "configured-index")
    configured_pyproject = configured / "pyproject.toml"
    configured_pyproject.write_text(
        configured_pyproject.read_text()
        + '\n[[tool.uv.index]]\nname = "private"\nurl = "https://example.com/simple"\n'
    )

    # Act
    mentioned_violation = check_contract(mentioned_pyproject)
    configured_violation = check_contract(configured_pyproject)

    # Assert
    assert mentioned_violation is None
    assert configured_violation is not None
    assert "tool.uv.index" in configured_violation


def test_repository_quality_reports_link_and_cross_file_mismatches(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    # Arrange
    example = _write_quality_repository(tmp_path, monkeypatch)
    assert check_repository_quality([example]) == {}

    readme = example / "README.md"
    readme.write_text(readme.read_text() + "\n[Missing](missing.md)\n")
    pyproject = example / "pyproject.toml"
    pyproject.write_text(
        pyproject.read_text().replace("pymediate-example-010-basic", "pymediate-example-wrong-name")
    )
    (tmp_path / "pymediate.code-workspace").write_text(
        '{"folders": [{"path": "examples/900-wrong"}]}\n'
    )
    devcontainer_path = tmp_path / ".devcontainer" / example.name / "devcontainer.json"
    devcontainer = json.loads(devcontainer_path.read_text())
    devcontainer["postCreateCommand"] = "uv lock"
    del devcontainer["features"]
    devcontainer_path.write_text(json.dumps(devcontainer))
    settings_path = example / ".vscode" / "settings.json"
    settings = json.loads(settings_path.read_text())
    del settings["python.testing.pytestEnabled"]
    settings_path.write_text(json.dumps(settings))

    # Act
    violations = check_repository_quality([example])

    # Assert
    assert (
        "pymediate.code-workspace must list every example in numeric order"
        in violations["repository"]
    )
    assert (
        "examples/010-basic/README.md has a broken relative link: missing.md"
        in violations[example.name]
    )
    assert "[project].name must be pymediate-example-010-basic" in violations[example.name]
    assert (
        "editor settings must enable the shared Ruff and pytest configuration"
        in violations[example.name]
    )
    assert "devcontainer must install the uv feature" in violations[example.name]
    assert "devcontainer postCreateCommand must be uv sync" in violations[example.name]


def test_repository_quality_reports_malformed_json(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    # Arrange
    example = _write_quality_repository(tmp_path, monkeypatch)
    (tmp_path / "pymediate.code-workspace").write_text("{")
    devcontainer = tmp_path / ".devcontainer" / example.name / "devcontainer.json"
    devcontainer.write_text("{")

    # Act
    violations = check_repository_quality([example])

    # Assert
    assert any(
        message.startswith("cannot read pymediate.code-workspace:")
        for message in violations["repository"]
    )
    assert any(
        message.startswith("cannot read devcontainer.json:") for message in violations[example.name]
    )


def test_repository_quality_requires_exact_headings_outside_code_fences(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    # Arrange
    example = _write_quality_repository(tmp_path, monkeypatch)
    readme = example / "README.md"
    readme.write_text(
        readme.read_text().replace("## Run\n", "## Running\n") + "\n```markdown\n## Run\n```\n"
    )

    # Act
    violations = check_repository_quality([example])

    # Assert
    assert "README is missing ## Run" in violations[example.name]


def test_repository_examples_meet_the_mechanical_quality_rules() -> None:
    assert check_repository_quality(discover_examples()) == {}


def test_release_copy_removes_the_checkout_source_before_repinning(tmp_path: Path) -> None:
    # Arrange
    source = _write_example(tmp_path, FLAGSHIP_EXAMPLE, PYMEDIATE_SOURCE_LINE)
    workspace = tmp_path / "release-copy"

    # Act
    copy_example_for_release(source, workspace)
    copied_pyproject = (workspace / "pyproject.toml").read_text()

    # Assert
    assert PYMEDIATE_SOURCE_LINE not in copied_pyproject
    assert 'dependencies = ["pymediate>=0.5.0"]' in copied_pyproject
