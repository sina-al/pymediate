#!/usr/bin/env python3
"""PostToolUse hook: auto-format Python files after Edit/Write.

Registered in .claude/settings.json on Edit|Write. Receives the tool-call JSON on stdin
and runs ruff format + ruff check --fix on the edited file, matching what `poe fix` does
repo-wide, so agent edits land already formatted.
"""

import json
import subprocess
import sys


def main() -> None:
    """Format the edited file with ruff when it's a Python file."""
    data = json.load(sys.stdin)
    path = data.get("tool_input", {}).get("file_path", "")
    if path.endswith(".py"):
        subprocess.run(["uv", "run", "ruff", "format", path], check=False)
        subprocess.run(["uv", "run", "ruff", "check", "--fix", path], check=False)


if __name__ == "__main__":
    main()
