"""Protect the flagship example's narrow current-checkout exception."""

from pathlib import Path

from scripts.run_examples import (
    FLAGSHIP_EXAMPLE,
    FLAGSHIP_PYMEDIATE_SOURCE_LINE,
    check_contract,
    copy_example_for_release,
)


def _write_example(tmp_path: Path, name: str, source_line: str) -> Path:
    example = tmp_path / name
    example.mkdir(parents=True)
    (example / "pyproject.toml").write_text(
        "[project]\n"
        f'name = "{name}"\n'
        'version = "0.1.0"\n'
        'dependencies = ["pymediate"]\n'
        "\n[tool.uv.sources]\n"
        f"{source_line}"
    )
    return example


def test_contract_allows_only_the_flagships_exact_checkout_source(tmp_path: Path) -> None:
    # Arrange
    flagship = _write_example(tmp_path / "valid", FLAGSHIP_EXAMPLE, FLAGSHIP_PYMEDIATE_SOURCE_LINE)
    wrong_source = _write_example(
        tmp_path / "wrong-source",
        FLAGSHIP_EXAMPLE,
        'pymediate = { path = "../source", editable = true }\n',
    )
    another_example = _write_example(tmp_path, "another-example", FLAGSHIP_PYMEDIATE_SOURCE_LINE)

    # Act
    flagship_violation = check_contract(flagship / "pyproject.toml")
    source_violation = check_contract(wrong_source / "pyproject.toml")
    other_violation = check_contract(another_example / "pyproject.toml")

    # Assert
    assert flagship_violation is None
    assert source_violation is not None
    assert "non-workspace" in source_violation
    assert other_violation is not None
    assert "non-workspace" in other_violation


def test_release_copy_removes_the_checkout_source_before_repinning(tmp_path: Path) -> None:
    # Arrange
    source = _write_example(tmp_path, FLAGSHIP_EXAMPLE, FLAGSHIP_PYMEDIATE_SOURCE_LINE)
    workspace = tmp_path / "release-copy"

    # Act
    copy_example_for_release(source, workspace)
    copied_pyproject = (workspace / "pyproject.toml").read_text()

    # Assert
    assert FLAGSHIP_PYMEDIATE_SOURCE_LINE not in copied_pyproject
    assert 'dependencies = ["pymediate"]' in copied_pyproject
