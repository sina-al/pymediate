#!/usr/bin/env python3
"""Summarize what changed since the last release and recommend minor vs. patch.

PyMediate follows ZeroVer (see CLAUDE.md's "Versioning" section): the major version stays
at 0 indefinitely, so MINOR is the number that has to carry the "breaking change" signal
SemVer would normally reserve for major, and PATCH is everything backward-compatible. This
script exists to make that call with evidence instead of a guess, for a human to confirm
during `/release`.

Neither signal alone is reliable enough to trust on its own:

- Commit messages (Conventional Commits, already enforced on PR titles by pr-checks.yml) are
  cheap to read and usually right, but they're only as accurate as whoever wrote them - a
  `fix:` commit can still remove a public method by accident, and `feat:` doesn't always mean
  "breaking" (plenty of new features are purely additive).
- A diff since the last tag is ground truth for what actually shipped, but scanning a whole
  diff for "did anything break" has no clear stopping rule.

So this script combines both: it classifies commits since the last tag by Conventional
Commit type (for a fast read of *intent*), and separately diffs the exact three surfaces
CLAUDE.md and CONTRIBUTING.md already single out as this project's own definition of
"breaking" - `__all__` in `src/pymediate/__init__.py`, `Handler`, and the `ServiceProvider`
protocol (for *evidence*). A recommendation follows from whichever signal is strongest, but
the full report is always printed so a human can override it.

Recommendation rules, in priority order:
    1. An explicit Conventional Commits breaking marker (`!` after the type/scope, or a
       `BREAKING CHANGE:` footer) -> minor, "explicit breaking-change marker".
    2. A name removed from `__all__` -> minor, "public export removed".
    3. A public class or method removed (not just added) from handler.py, aio/handler.py, or
       service.py -> minor, "possible signature change in a flagged breaking-change surface".
       This is symbol-level, via `ast` on the file at each revision - not a textual diff grep,
       because a textual grep for removed `def`/`class` lines also matches lines inside a
       removed docstring's example code block (e.g. an old `Architecture Notes` sample), which
       produced a false "minor" recommendation in testing even though nothing in the real API
       had changed. Parsing the AST at both revisions and comparing symbol names sidesteps that
       - string content, including code fences inside a docstring, is never treated as code.
    4. Any `feat:` commit that touches `src/pymediate/` (the shipped package - a `feat:` to
       scripts/, docs/, or repo config never reaches an installed `pip install pymediate`, so
       it isn't a new feature from a consumer's perspective), with no signal above -> minor,
       "new functionality added".
    5. Otherwise -> patch, "no breaking surface or new feature detected".

Usage:
    python3 scripts/release_impact.py                  # last tag -> HEAD
    python3 scripts/release_impact.py --from v0.1.0     # explicit start point
    python3 scripts/release_impact.py --from v0.1.0 --to v0.1.1   # compare two releases
"""

from __future__ import annotations

import argparse
import ast
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# The breaking-change surfaces CLAUDE.md ("Quality bar") and CONTRIBUTING.md already name.
BREAKING_SURFACE_FILES = [
    "src/pymediate/__init__.py",
    "src/pymediate/handler.py",
    "src/pymediate/aio/handler.py",
    "src/pymediate/service.py",
]

CONVENTIONAL_COMMIT_RE = re.compile(
    r"^(?P<type>[a-zA-Z]+)(?:\([^)]*\))?(?P<breaking>!)?:\s*(?P<desc>.+)$"
)
RECORD_SEP = "\x1e"
FIELD_SEP = "\x1f"


@dataclass
class Commit:
    sha: str
    subject: str
    body: str
    type: str | None
    breaking: bool
    description: str
    touches_package: bool


@dataclass
class Assessment:
    recommendation: str  # "minor" or "patch"
    reasons: list[str] = field(default_factory=list)


def run_git(*args: str) -> str:
    result = subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed:\n{result.stderr}")
    return result.stdout


def last_tag() -> str:
    return run_git("describe", "--tags", "--abbrev=0").strip()


def commit_touches_package(sha: str) -> bool:
    """Check whether a commit changed anything under src/pymediate/ (the shipped package).

    A `feat:` commit that only touches scripts/, docs/, or repo config (like this very
    script's own introduction) never reaches an installed `pip install pymediate` - it isn't
    a new feature from a consumer's perspective, so it shouldn't trigger a minor bump.
    """
    changed = run_git("diff-tree", "--no-commit-id", "--name-only", "-r", sha)
    return any(line.startswith("src/pymediate/") for line in changed.splitlines())


def commits_since(rev_range: str) -> list[Commit]:
    log = run_git(
        "log",
        rev_range,
        f"--format=%H{FIELD_SEP}%s{FIELD_SEP}%b{RECORD_SEP}",
    )
    commits = []
    for record in log.split(RECORD_SEP):
        record = record.strip("\n")
        if not record:
            continue
        sha, subject, body = record.split(FIELD_SEP)
        match = CONVENTIONAL_COMMIT_RE.match(subject)
        commit_type = match.group("type").lower() if match else None
        header_breaking = bool(match.group("breaking")) if match else False
        body_breaking = "BREAKING CHANGE" in body or "BREAKING-CHANGE" in body
        commits.append(
            Commit(
                sha=sha[:10],
                subject=subject,
                body=body.strip(),
                type=commit_type,
                breaking=header_breaking or body_breaking,
                description=match.group("desc") if match else subject,
                touches_package=commit_touches_package(sha),
            )
        )
    return commits


def file_at_rev(rev: str, path: str) -> str | None:
    result = subprocess.run(
        ["git", "show", f"{rev}:{path}"], cwd=REPO_ROOT, capture_output=True, text=True
    )
    return result.stdout if result.returncode == 0 else None


def extract_all_list(source: str) -> list[str]:
    """Pull the __all__ list's literal contents out of a module's source."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets
        ):
            names: list[str] = ast.literal_eval(node.value)
            return names
    return []


def diff_all(from_rev: str, to_rev: str) -> tuple[list[str], list[str]]:
    """Return (added, removed) export names in __all__ between two revisions."""
    before_src = file_at_rev(from_rev, "src/pymediate/__init__.py")
    after_src = file_at_rev(to_rev, "src/pymediate/__init__.py")
    before = set(extract_all_list(before_src)) if before_src else set()
    after = set(extract_all_list(after_src)) if after_src else set()
    return sorted(after - before), sorted(before - after)


def public_symbols(source: str) -> set[str]:
    """Collect dotted names of public top-level classes/functions and public class methods.

    AST-based, not a text search - a string literal (including a docstring's example code
    block) is never mistaken for an actual `def`/`class` statement, unlike a line-based diff.
    """
    tree = ast.parse(source)
    symbols: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            symbols.add(node.name)
            for child in node.body:
                if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef) and (
                    not child.name.startswith("_") or child.name.startswith("__")
                ):
                    symbols.add(f"{node.name}.{child.name}")
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and not node.name.startswith(
            "_"
        ):
            symbols.add(node.name)
    return symbols


def removed_defs_in_surface(from_rev: str, to_rev: str) -> dict[str, list[str]]:
    """For each breaking-surface file, list public symbols present before but missing after."""
    removed_by_file: dict[str, list[str]] = {}
    for rel_path in BREAKING_SURFACE_FILES:
        before_src = file_at_rev(from_rev, rel_path)
        after_src = file_at_rev(to_rev, rel_path)
        if before_src is None or after_src is None:
            continue
        before = public_symbols(before_src)
        after = public_symbols(after_src)
        removed = sorted(before - after)
        if removed:
            removed_by_file[rel_path] = removed
    return removed_by_file


def assess(
    commits: list[Commit],
    added: list[str],
    removed: list[str],
    removed_defs: dict[str, list[str]],
) -> Assessment:
    reasons = []

    explicit_breaking = [c for c in commits if c.breaking]
    if explicit_breaking:
        for c in explicit_breaking:
            reasons.append(f'explicit breaking-change marker on {c.sha} "{c.subject}"')
        return Assessment("minor", reasons)

    if removed:
        reasons.append(f"removed from __all__: {', '.join(removed)}")
        return Assessment("minor", reasons)

    if removed_defs:
        for rel_path, names in removed_defs.items():
            reasons.append(f"removed public symbol(s) in {rel_path}: {', '.join(names)}")
        return Assessment("minor", reasons)

    feats = [c for c in commits if c.type == "feat" and c.touches_package]
    if feats:
        for c in feats:
            reasons.append(f'new feature: {c.sha} "{c.description}"')
        return Assessment("minor", reasons)

    if not commits:
        reasons.append("no commits since the last tag")
    else:
        reasons.append("only fixes/docs/chores/refactors - no breaking surface or new feature")
    return Assessment("patch", reasons)


def print_report(
    from_rev: str,
    to_rev: str,
    commits: list[Commit],
    added: list[str],
    removed: list[str],
    removed_defs: dict[str, list[str]],
    result: Assessment,
) -> None:
    print(f"Comparing {from_rev}..{to_rev}\n")

    if not commits:
        print("No commits in range.\n")
    else:
        by_type: dict[str, list[Commit]] = {}
        for c in commits:
            by_type.setdefault(c.type or "other", []).append(c)
        print(f"Commits ({len(commits)}):")
        for commit_type, group in sorted(by_type.items()):
            print(f"  {commit_type} ({len(group)}):")
            for c in group:
                marker = " [BREAKING]" if c.breaking else ""
                marker += "" if c.touches_package else " [no package changes]"
                print(f"    {c.sha}  {c.description}{marker}")
        print()

    print("__all__ (src/pymediate/__init__.py):")
    print(f"  added:   {added or '(none)'}")
    print(f"  removed: {removed or '(none)'}")
    print()

    print("Breaking-surface files (__init__.py, handler.py, aio/handler.py, service.py):")
    if removed_defs:
        for rel_path, names in removed_defs.items():
            print(f"  {rel_path}:")
            for name in names:
                print(f"    - {name}")
    else:
        print("  (no removed public symbols)")
    print()

    print(f"RECOMMENDATION: {result.recommendation}")
    for reason in result.reasons:
        print(f"  - {reason}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--from", dest="from_rev", default=None, help="start ref (default: last tag)"
    )
    parser.add_argument("--to", dest="to_rev", default="HEAD", help="end ref (default: HEAD)")
    args = parser.parse_args()

    from_rev = args.from_rev or last_tag()
    to_rev = args.to_rev

    commits = commits_since(f"{from_rev}..{to_rev}")
    added, removed = diff_all(from_rev, to_rev)
    removed_defs = removed_defs_in_surface(from_rev, to_rev)
    result = assess(commits, added, removed, removed_defs)

    print_report(from_rev, to_rev, commits, added, removed, removed_defs, result)


if __name__ == "__main__":
    main()
