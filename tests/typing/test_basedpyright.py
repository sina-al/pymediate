"""Basedpyright type safety tests for pymediate users.

The basedpyright half of the cross-checker harness (see test_mypy.py for the
mypy half). Both halves run the same shared snippet corpus:

1. Every valid/ snippet must be completely clean - zero errors AND zero
   warnings - in both checking modes, so pyright and basedpyright users get
   the same first-class experience the mypy suite guarantees.
2. Every errors/ snippet must be flagged, with the specific rule pinned in
   expectations.py.
3. The public API must be 100% type-complete per --verifytypes, so no
   pymediate symbol ever resolves as Unknown in a user's editor. Incomplete
   type information in third-party packages is excluded from that measure.

Modes:
- "standard": vanilla pyright parity - what a plain pyright user sees.
- "recommended": basedpyright's strictest default - what a based user sees.

Each mode runs once per session against its checked-in config
(basedpyright_<mode>.json); tests then assert per-snippet outcomes.
"""

import functools
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.typing.expectations import (
    EXPECTED_BASEDPYRIGHT_RULES,
    EXPECTED_MYPY_CODES,
    RECOMMENDED_MODE_WARNING_ONLY,
)

HERE = Path(__file__).parent
SNIPPETS_DIR = HERE / "snippets"
VALID_DIR = SNIPPETS_DIR / "valid"
ERRORS_DIR = SNIPPETS_DIR / "errors"

MODES = ("standard", "recommended")

# Pin the exact checker version: diagnostics (rules, severities, message text)
# drift across releases, so an upgrade must be a deliberate act - bump this
# constant together with `uv lock --upgrade-package basedpyright` and re-review
# the corpus, never one without the other.
PINNED_BASEDPYRIGHT_VERSION = "1.39.9"


def get_snippet_files(directory: Path) -> list[Path]:
    """Get all Python snippet files from a directory."""
    return sorted(directory.glob("*.py"))


def basedpyright_executable() -> str:
    """Resolve the basedpyright CLI from the active environment."""
    exe = shutil.which("basedpyright")
    assert exe is not None, (
        "basedpyright not found - install the test dependency group "
        "(uv sync --all-extras --group test)"
    )
    return exe


@functools.cache
def run_basedpyright(mode: str) -> dict[str, list[dict[str, str]]]:
    """Run basedpyright over the snippet corpus in the given mode, once per session.

    Returns a mapping of snippet path (relative to the snippets dir, e.g.
    "valid/basic_type_inference.py") to its diagnostics, each reduced to
    {"severity": ..., "rule": ..., "line": ...}.
    """
    config = HERE / f"basedpyright_{mode}.json"
    result = subprocess.run(  # noqa: S603 - fixed argv, no shell
        [basedpyright_executable(), "--outputjson", "-p", str(config)],
        capture_output=True,
        text=True,
        check=False,
    )
    output = json.loads(result.stdout)

    expected_count = len(get_snippet_files(VALID_DIR)) + len(get_snippet_files(ERRORS_DIR))
    analyzed = output["summary"]["filesAnalyzed"]
    assert analyzed == expected_count, (
        f"basedpyright analyzed {analyzed} files, expected {expected_count} - "
        f"is the 'include' in {config.name} still pointing at the snippets?"
    )

    diagnostics: dict[str, list[dict[str, str]]] = {}
    for diag in output["generalDiagnostics"]:
        key = Path(diag["file"]).relative_to(SNIPPETS_DIR).as_posix()
        diagnostics.setdefault(key, []).append(
            {
                "severity": diag["severity"],
                "rule": diag.get("rule", "<no-rule>"),
                "line": str(diag["range"]["start"]["line"] + 1),
            }
        )
    return diagnostics


def format_diagnostics(diags: list[dict[str, str]]) -> str:
    """Render diagnostics for assertion messages."""
    return "\n".join(f"  L{d['line']} {d['severity']}: {d['rule']}" for d in diags) or "  (none)"


class TestValidUsageIsClean:
    """Valid usage must be spotless for pyright and based users alike."""

    @pytest.mark.parametrize("mode", MODES)
    @pytest.mark.parametrize("snippet_file", get_snippet_files(VALID_DIR), ids=lambda p: p.stem)
    def test_valid_snippet_has_no_diagnostics(self, snippet_file: Path, mode: str) -> None:
        """Valid snippets produce zero errors and zero warnings in every mode."""
        diags = run_basedpyright(mode).get(f"valid/{snippet_file.name}", [])
        assert diags == [], (
            f"{snippet_file.name} should be clean under basedpyright ({mode} mode), "
            f"but produced:\n{format_diagnostics(diags)}"
        )


class TestInvalidUsageIsFlagged:
    """Every errors/ snippet must be caught, with the expected rule."""

    @pytest.mark.parametrize("mode", MODES)
    @pytest.mark.parametrize("snippet_file", get_snippet_files(ERRORS_DIR), ids=lambda p: p.stem)
    def test_error_snippet_raises_expected_rules(self, snippet_file: Path, mode: str) -> None:
        """Error snippets are flagged with the rules pinned in expectations.py."""
        diags = run_basedpyright(mode).get(f"errors/{snippet_file.name}", [])
        expected = EXPECTED_BASEDPYRIGHT_RULES[snippet_file.stem]

        observed_rules = {d["rule"] for d in diags}
        missing = expected - observed_rules
        assert not missing, (
            f"{snippet_file.name} should raise {sorted(missing)} under basedpyright "
            f"({mode} mode), but produced only:\n{format_diagnostics(diags)}"
        )

        warning_only = mode == "recommended" and snippet_file.stem in RECOMMENDED_MODE_WARNING_ONLY
        if warning_only:
            # Pinned severity demotion - see RECOMMENDED_MODE_WARNING_ONLY. If this
            # starts failing because an error appeared, the divergence has closed:
            # remove the file from that set rather than weakening the assertion.
            assert not any(d["severity"] == "error" for d in diags), (
                f"{snippet_file.name} now raises error-severity diagnostics in "
                f"recommended mode - remove it from RECOMMENDED_MODE_WARNING_ONLY:\n"
                f"{format_diagnostics(diags)}"
            )
        else:
            assert any(d["severity"] == "error" for d in diags), (
                f"{snippet_file.name} should produce at least one error-severity "
                f"diagnostic under basedpyright ({mode} mode), but produced:\n"
                f"{format_diagnostics(diags)}"
            )


class TestExpectationsCoverCorpus:
    """The expectations tables and the errors/ corpus must stay in lockstep."""

    def test_tables_match_error_snippets(self) -> None:
        """Every errors/ snippet has expectations for both checkers, and vice versa."""
        stems = {p.stem for p in get_snippet_files(ERRORS_DIR)}
        assert set(EXPECTED_MYPY_CODES) == stems
        assert set(EXPECTED_BASEDPYRIGHT_RULES) == stems
        assert RECOMMENDED_MODE_WARNING_ONLY <= stems


class TestBasedpyrightConfiguration:
    """Guard the harness's own preconditions."""

    def test_pinned_version(self) -> None:
        """The exact basedpyright version is pinned - upgrades must be deliberate."""
        result = subprocess.run(  # noqa: S603 - fixed argv, no shell
            [basedpyright_executable(), "--version"],
            capture_output=True,
            text=True,
            check=True,
        )
        assert result.stdout.startswith(f"basedpyright {PINNED_BASEDPYRIGHT_VERSION}"), (
            f"basedpyright version changed: {result.stdout.strip()!r}. Diagnostics can "
            f"drift across releases - re-review the snippet corpus in both modes, then "
            f"update PINNED_BASEDPYRIGHT_VERSION."
        )


class TestPublicApiTypeCompleteness:
    """No pymediate symbol may resolve as Unknown in a user's editor."""

    def test_verifytypes_is_total(self) -> None:
        """Our public API is 100% complete, excluding third-party stub defects."""
        result = subprocess.run(  # noqa: S603 - fixed argv, no shell
            [
                basedpyright_executable(),
                "--verifytypes",
                "pymediate",
                "--ignoreexternal",
                "--outputjson",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        completeness = json.loads(result.stdout)["typeCompleteness"]
        unknown = [
            symbol["name"] for symbol in completeness["symbols"] if not symbol["isTypeKnown"]
        ]
        score = completeness["completenessScore"]
        assert score == 1.0, (
            f"Public API type completeness dropped to {score:.2%}; "
            f"symbols with unknown types:\n" + "\n".join(f"  {name}" for name in unknown)
        )
