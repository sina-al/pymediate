#!/usr/bin/env python3
"""PreToolUse hook: inject point-of-edit reminders for sensitive paths.

Registered in .claude/settings.json on Edit|Write. Receives the tool-call JSON on stdin;
when the edited file matches a guarded path, prints hookSpecificOutput JSON whose
additionalContext is fed back to the model at the moment of the edit. Silent otherwise.

Add a guard by appending a (path-fragment, message) pair to REMINDERS. First match wins.
"""

import json
import sys

REMINDERS = [
    (
        ".github/workflows/",
        "This touches a GitHub Actions workflow. zizmor owns the mechanical security bar - "
        "run `uv run poe actions:lint` after editing (checks.yml enforces it in CI); its "
        "audits cover action pinning, template injection, permissions, dangerous triggers, "
        "and trusted publishing. What it cannot lint, you must judge: scope triggers "
        "narrowly (paths/branches filters plus a concurrency group), prefer workflow_run "
        "privilege separation over pull_request_target wherever secrets meet fork code, "
        "and treat adding any new third-party action as a design decision, not a "
        "convenience. Also apply the poe-vs-inline criteria (CLAUDE.md, section: poe tasks "
        "vs. inline workflow steps): before writing a run: command, check tasks.toml - if "
        "an existing poe task wraps it, route it through the task rather than copying a "
        "neighboring raw step.",
    ),
    (
        "tests/typing/snippets/",
        "This touches the typing-snippet test system (see CLAUDE.md). Files under "
        "tests/typing/snippets/errors/ are DELIBERATELY type-invalid: never fix the type "
        "error, never add type: ignore, never exclude them in mypy.ini or the basedpyright "
        "configs. Adding or removing an errors case means updating BOTH checker tables in "
        "tests/typing/expectations.py (a sync test fails otherwise). valid/ snippets must "
        "pass mypy --strict, produce zero errors and zero warnings under basedpyright "
        "recommended mode, and execute at runtime (async ones define async def main).",
    ),
]


def main() -> None:
    """Print additionalContext JSON if the edited file matches a guarded path."""
    data = json.load(sys.stdin)
    path = data.get("tool_input", {}).get("file_path", "")
    for fragment, message in REMINDERS:
        if fragment in path:
            output = {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow",
                    "additionalContext": message,
                }
            }
            print(json.dumps(output))
            return


if __name__ == "__main__":
    main()
