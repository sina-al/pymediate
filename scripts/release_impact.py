#!/usr/bin/env python3
"""Summarize what changed since the last release and recommend minor vs. patch.

PyMediate follows ZeroVer (see CLAUDE.md's "Versioning" section): the major version stays
at 0 indefinitely, so MINOR is the number that has to carry the "breaking change" signal
SemVer would normally reserve for major, and PATCH is everything backward-compatible. This
script exists to make that call with evidence instead of a guess, for a human to confirm
during `/release`.

Neither signal alone is reliable enough to trust on its own:

- Commit messages (Conventional Commits, already enforced on PR titles by pr.yml) are
  cheap to read and usually right, but they're only as accurate as whoever wrote them - a
  `fix:` commit can still remove a public method by accident, and `feat:` doesn't always mean
  "breaking" (plenty of new features are purely additive).
- A diff since the last tag is ground truth for what actually shipped, but scanning a whole
  diff for "did anything break" has no clear stopping rule.

So this script combines both: it classifies commits since the last tag by Conventional
Commit type (for a fast read of *intent*), and separately runs `griffe check` - the same
public-API differ this repo uses in CI (`poe api:check`, .github/workflows/pr.yml) - to
detect what actually broke at the signature level (for *evidence*), plus a cheap pure-git
check for names dropped from `__all__` as an offline fast-path. A recommendation follows
from whichever signal is strongest, but the full report is always printed so a human can
override it.

Recommendation rules, in priority order:
    1. An explicit Conventional Commits breaking marker (`!` after the type/scope, or a
       `BREAKING CHANGE:` footer) -> minor, "explicit breaking-change marker".
    2. A name removed from `__all__` -> minor, "public export removed".
    3. A signature-level public-API break reported by `griffe check` (a removed or changed
       public class/function/method/attribute anywhere in the package) -> minor. This reuses
       the repo's own breaking-change tool rather than a hand-rolled AST diff, so it catches
       changed signatures - not only removals - and pinpoints the exact symbol and line.
       griffe writes findings to stderr and does not exit non-zero for them, so the signal is
       stderr lines matching a "path:line:" finding shape. griffe can be over-eager (it flags
       e.g. a public constant's value changing); that's why the full report is printed and a
       human confirms - over-recommending minor is the safe direction under ZeroVer.
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

# griffe check invocation, pinned to match this repo's CI breaking-change check
# (see the `api:check` poe task and .github/workflows/pr.yml).
GRIFFE_CHECK = ["uvx", "--from", "griffe==2.1.0", "griffe", "check", "pymediate", "-s", "src"]

# A griffe finding line looks like "src/pymediate/foo.py:12: Symbol: message".
GRIFFE_FINDING_RE = re.compile(r"^\S+:\d+:")

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


def griffe_breaking_changes(from_rev: str, to_rev: str) -> list[str]:
    """Signature-level public-API breaking changes between two revisions, via `griffe check`.

    Reuses this repo's CI breaking-change tool (`poe api:check`) instead of a bespoke AST
    diff, so it catches changed signatures - not only removed symbols - anywhere in the
    public API. Compares `from_rev` (older) against `to_rev` (newer; the working tree when
    that's HEAD). griffe writes findings to stderr and does not set a non-zero exit for them,
    so the signal is stderr lines matching the "path:line:" finding shape.
    """
    cmd = [*GRIFFE_CHECK, "-a", from_rev]
    if to_rev not in ("HEAD", ""):
        cmd += ["-b", to_rev]
    result = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)
    return [
        line.strip() for line in result.stderr.splitlines() if GRIFFE_FINDING_RE.match(line.strip())
    ]


def assess(
    commits: list[Commit],
    added: list[str],
    removed: list[str],
    breaking_changes: list[str],
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

    if breaking_changes:
        for change in breaking_changes:
            reasons.append(f"public API break (griffe): {change}")
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
    breaking_changes: list[str],
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

    print("Public API breaking changes (griffe check):")
    if breaking_changes:
        for change in breaking_changes:
            print(f"  - {change}")
    else:
        print("  (none detected)")
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
    breaking_changes = griffe_breaking_changes(from_rev, to_rev)
    result = assess(commits, added, removed, breaking_changes)

    print_report(from_rev, to_rev, commits, added, removed, breaking_changes, result)


if __name__ == "__main__":
    main()
