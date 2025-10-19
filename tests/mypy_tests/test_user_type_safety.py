"""
Comprehensive mypy type safety tests for pymediate users.

These tests verify that:
1. Valid pymediate usage passes mypy type checking
2. Invalid pymediate usage is caught by mypy with appropriate errors

The tests run mypy programmatically on code snippets to ensure the library
provides proper type safety for end users.
"""

from pathlib import Path

import pytest
from mypy import api as mypy_api

# Path to test snippets
SNIPPETS_DIR = Path(__file__).parent / "snippets"
VALID_DIR = SNIPPETS_DIR / "valid"
ERRORS_DIR = SNIPPETS_DIR / "errors"


def run_mypy_on_file(file_path: Path, strict: bool = True) -> tuple[int, str, str]:
    """
    Run mypy on a file and return exit code, stdout, and stderr.

    Uses the mypy API directly for better performance and integration.

    Args:
        file_path: Path to the Python file to check
        strict: Whether to use strict mode (default: True)

    Returns:
        Tuple of (exit_code, stdout, stderr)
    """
    args = [
        str(file_path),
        "--show-error-codes",
        "--no-error-summary",
    ]

    if strict:
        args.append("--strict")

    # mypy.api.run returns (stdout, stderr, exit_code)
    stdout, stderr, exit_code = mypy_api.run(args)

    return exit_code, stdout, stderr


def get_snippet_files(directory: Path) -> list[Path]:
    """Get all Python snippet files from a directory."""
    return sorted(directory.glob("*.py"))


class TestValidUsagePassesMypy:
    """Test that valid pymediate usage passes mypy type checking."""

    @pytest.mark.parametrize(
        "snippet_file",
        get_snippet_files(VALID_DIR),
        ids=lambda p: p.stem,
    )
    def test_valid_snippet_passes_mypy(self, snippet_file: Path) -> None:
        """Valid usage snippets should pass mypy without errors."""
        exit_code, stdout, stderr = run_mypy_on_file(snippet_file, strict=True)

        # Mypy should succeed (exit code 0)
        assert exit_code == 0, (
            f"Expected {snippet_file.name} to pass mypy, but it failed.\n"
            f"stdout:\n{stdout}\n"
            f"stderr:\n{stderr}"
        )

        # Should have "Success" message (when no errors)
        assert "Success" in stdout or stdout.strip() == "", (
            f"Expected success message for {snippet_file.name}.\nstdout:\n{stdout}"
        )


class TestInvalidUsageFailsMypy:
    """Test that invalid pymediate usage is caught by mypy."""

    @pytest.mark.parametrize(
        "snippet_file",
        get_snippet_files(ERRORS_DIR),
        ids=lambda p: p.stem,
    )
    def test_error_snippet_fails_mypy(self, snippet_file: Path) -> None:
        """Error snippets should fail mypy type checking."""
        exit_code, stdout, stderr = run_mypy_on_file(snippet_file, strict=True)

        # Mypy should fail (exit code 1)
        assert exit_code == 1, (
            f"Expected {snippet_file.name} to fail mypy, but it passed.\n"
            f"This snippet should have type errors.\n"
            f"stdout:\n{stdout}\n"
            f"stderr:\n{stderr}"
        )

        # Should have error output
        assert stdout.strip() != "", (
            f"Expected mypy errors for {snippet_file.name}, but got no output.\nstderr:\n{stderr}"
        )


class TestSpecificErrorScenarios:
    """Test specific error scenarios with detailed error checking."""

    def test_wrong_response_attribute_error(self) -> None:
        """Accessing non-existent attribute should raise attr-defined error."""
        file_path = ERRORS_DIR / "wrong_response_attribute.py"
        exit_code, stdout, stderr = run_mypy_on_file(file_path)

        assert exit_code == 1
        assert 'has no attribute "email"' in stdout or "attr-defined" in stdout

    def test_wrong_response_type_assignment_error(self) -> None:
        """Assigning wrong response type should raise assignment error."""
        file_path = ERRORS_DIR / "wrong_response_type_assignment.py"
        exit_code, stdout, stderr = run_mypy_on_file(file_path)

        assert exit_code == 1
        assert "assignment" in stdout.lower() or "incompatible type" in stdout.lower()

    def test_optional_without_none_check_error(self) -> None:
        """Using optional field without None check should raise union-attr error."""
        file_path = ERRORS_DIR / "optional_without_none_check.py"
        exit_code, stdout, stderr = run_mypy_on_file(file_path)

        assert exit_code == 1
        assert "union-attr" in stdout or "Optional" in stdout or "None" in stdout

    def test_union_type_without_narrowing_error(self) -> None:
        """Accessing union type field without narrowing should raise union-attr error."""
        file_path = ERRORS_DIR / "union_type_without_narrowing.py"
        exit_code, stdout, stderr = run_mypy_on_file(file_path)

        assert exit_code == 1
        assert "union-attr" in stdout

    def test_mediator_send_wrong_expectation_error(self) -> None:
        """Expecting wrong response type from send() should fail mypy."""
        file_path = ERRORS_DIR / "mediator_send_wrong_expectation.py"
        exit_code, stdout, stderr = run_mypy_on_file(file_path)

        assert exit_code == 1
        assert "assignment" in stdout.lower() or "incompatible" in stdout.lower()


class TestTypeSafetyScenarios:
    """Test type safety scenarios that only mypy can verify."""

    def test_basic_type_inference(self) -> None:
        """Mediator.send() should infer response type correctly."""
        file_path = VALID_DIR / "basic_type_inference.py"
        exit_code, stdout, stderr = run_mypy_on_file(file_path, strict=True)

        assert exit_code == 0, (
            f"Basic type inference should pass strict mypy.\nstdout:\n{stdout}\nstderr:\n{stderr}"
        )

    def test_resolver_type_inference(self) -> None:
        """Resolver.resolve() should return correctly typed handler."""
        file_path = VALID_DIR / "resolver_type_inference.py"
        exit_code, stdout, stderr = run_mypy_on_file(file_path, strict=True)

        assert exit_code == 0, (
            f"Resolver type inference should pass strict mypy.\n"
            f"stdout:\n{stdout}\n"
            f"stderr:\n{stderr}"
        )

    def test_optional_type_narrowing(self) -> None:
        """Optional fields with proper None checking should pass."""
        file_path = VALID_DIR / "optional_fields.py"
        exit_code, stdout, stderr = run_mypy_on_file(file_path, strict=True)

        assert exit_code == 0, (
            f"Optional fields with None checks should pass strict mypy.\n"
            f"stdout:\n{stdout}\n"
            f"stderr:\n{stderr}"
        )

    def test_union_type_narrowing(self) -> None:
        """Union types with proper type narrowing should pass."""
        file_path = VALID_DIR / "union_types.py"
        exit_code, stdout, stderr = run_mypy_on_file(file_path, strict=True)

        assert exit_code == 0, (
            f"Union types with narrowing should pass strict mypy.\n"
            f"stdout:\n{stdout}\n"
            f"stderr:\n{stderr}"
        )

    def test_nested_complex_types(self) -> None:
        """Nested complex types should maintain type safety."""
        file_path = VALID_DIR / "nested_types.py"
        exit_code, stdout, stderr = run_mypy_on_file(file_path, strict=True)

        assert exit_code == 0, (
            f"Nested complex types should pass strict mypy.\nstdout:\n{stdout}\nstderr:\n{stderr}"
        )

    def test_void_none_response(self) -> None:
        """Void/None responses should type check correctly."""
        file_path = VALID_DIR / "void_response.py"
        exit_code, stdout, stderr = run_mypy_on_file(file_path, strict=True)

        assert exit_code == 0, (
            f"Void/None responses should pass strict mypy.\nstdout:\n{stdout}\nstderr:\n{stderr}"
        )


class TestMypyConfiguration:
    """Test that mypy is properly configured for the test suite."""

    def test_mypy_available(self) -> None:
        """Mypy should be available in the test environment."""
        # Test that we can use the mypy API
        stdout, stderr, exit_code = mypy_api.run(["--version"])
        assert exit_code == 0, "mypy should be installed and available"
        assert "mypy" in stdout.lower(), "mypy version should be displayed"

    def test_strict_mode_enabled(self) -> None:
        """Verify strict mode catches type errors."""
        # Use an error file that should fail strict mode
        file_path = ERRORS_DIR / "optional_without_none_check.py"
        exit_code, stdout, stderr = run_mypy_on_file(file_path, strict=True)

        # Strict mode should catch the error
        assert exit_code == 1
        assert "union-attr" in stdout or "None" in stdout


# Summary test to give an overview
def test_comprehensive_coverage_summary() -> None:
    """
    Summary test showing total coverage of valid and error cases.

    This test provides a quick overview of how many test cases we have.
    """
    valid_files = get_snippet_files(VALID_DIR)
    error_files = get_snippet_files(ERRORS_DIR)

    print(f"\n{'=' * 60}")
    print("Mypy Type Safety Test Coverage Summary")
    print(f"{'=' * 60}")
    print(f"Valid usage snippets: {len(valid_files)}")
    for f in valid_files:
        print(f"  ✓ {f.stem}")

    print(f"\nError detection snippets: {len(error_files)}")
    for f in error_files:
        print(f"  ✗ {f.stem}")

    print(f"\nTotal test scenarios: {len(valid_files) + len(error_files)}")
    print(f"{'=' * 60}\n")

    # Ensure we have focused coverage on mypy-specific type safety
    assert len(valid_files) >= 5, "Should have at least 5 valid type safety patterns"
    assert len(error_files) >= 4, "Should have at least 4 error detection scenarios"
