#!/usr/bin/env python3
"""Regenerate .claude/context/api-signatures.md from src/pymediate/.

Walks the public modules of src/pymediate/ with griffe (a direct dev-group dependency)
and renders a signatures-only, docstring-summary blueprint: class/function signatures with
no implementation bodies, one-line docstring summaries, no private (``_``-prefixed)
members, and nothing from pymediate._internal (no public API guarantees, per CLAUDE.md).

The output file is entirely generated — CLAUDE.md pulls it in via Claude Code's
``@path/to/file`` import syntax, so it's part of the loaded context without mixing
generated content into the hand-written CLAUDE.md itself.

Usage:
    python3 scripts/update_context.py
    python3 scripts/update_context.py --check   # exit 1 if the file would change
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import griffe
from griffe import Alias, Class, Function, Module, ParameterKind

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / ".claude" / "context" / "api-signatures.md"
SRC = ROOT / "src"

# Public surface, in the order they should appear. Anything under pymediate._internal
# is deliberately excluded (see CLAUDE.md: "no public API, no back-compat guarantees").
MODULES = [
    "pymediate",
    "pymediate.request",
    "pymediate.event",
    "pymediate.handler",
    "pymediate.mediator",
    "pymediate.pipeline",
    "pymediate.service",
    "pymediate.errors",
    "pymediate.providers.dependency_injector",
    "pymediate.sync",
    "pymediate.sync.event",
    "pymediate.sync.handler",
    "pymediate.sync.mediator",
    "pymediate.sync.pipeline",
]

# Dunder methods worth showing on a class even though they're "private" by name.
PUBLIC_DUNDERS = {"__init__", "__call__"}


def is_public(name: str) -> bool:
    """Whether a member name belongs on the blueprint."""
    return not name.startswith("_") or name in PUBLIC_DUNDERS


def docstring_summary(obj: Class | Function) -> str | None:
    """First line of a docstring, if any."""
    if obj.docstring is None:
        return None
    first_line = obj.docstring.value.strip().splitlines()[0].strip()
    return first_line or None


def render_signature(func: Function) -> str:
    """Reconstruct a ``[async] def name(...) -> returns:`` line from griffe's parsed parameters."""
    parts: list[str] = []
    prev_kind = None
    for param in func.parameters:
        if param.kind is ParameterKind.keyword_only and prev_kind is not ParameterKind.keyword_only:
            parts.append("*")
        piece = param.name
        if param.kind is ParameterKind.var_positional:
            piece = f"*{piece}"
        elif param.kind is ParameterKind.var_keyword:
            piece = f"**{piece}"
        if param.annotation is not None:
            piece += f": {param.annotation}"
        if param.default is not None and param.kind not in (
            ParameterKind.var_positional,
            ParameterKind.var_keyword,
        ):
            piece += f" = {param.default}"
        parts.append(piece)
        prev_kind = param.kind
    returns = f" -> {func.returns}" if func.returns is not None else ""
    keyword = "async def" if "async" in func.labels else "def"
    return f"{keyword} {func.name}({', '.join(parts)}){returns}:"


def render_function(func: Function, indent: str) -> list[str]:
    lines = []
    for decorator in ("abstractmethod", "classmethod", "staticmethod", "property"):
        if decorator in func.labels:
            lines.append(f"{indent}@{decorator}")
    lines.append(f"{indent}{render_signature(func)}")
    summary = docstring_summary(func)
    if summary:
        lines.append(f'{indent}    """{summary}"""')
    lines.append(f"{indent}    ...")
    return lines


def render_class(cls: Class) -> list[str]:
    bases = ", ".join(str(base) for base in cls.bases)
    header = f"class {cls.name}({bases}):" if bases else f"class {cls.name}:"
    lines = [header]
    summary = docstring_summary(cls)
    if summary:
        lines.append(f'    """{summary}"""')

    members = [
        m
        for m in cls.members.values()
        if isinstance(m, Function) and is_public(m.name) and m.parent is cls
    ]
    if not members:
        lines.append("    ...")
        return lines
    for member in members:
        lines.extend(render_function(member, indent="    "))
    return lines


def render_module(module: Module) -> list[str]:
    if module.name == "pymediate" or module.name == "sync":
        # Top-level packages only re-export names defined (and rendered) elsewhere;
        # list the re-exports instead of repeating full definitions.
        exported = [str(name) for name in module.exports or [] if is_public(str(name))]
        return [f"# Re-exports: {', '.join(exported)}"] if exported else []

    lines: list[str] = []
    for member in module.members.values():
        if isinstance(member, Alias) or not is_public(member.name):
            continue
        if isinstance(member, Class):
            lines.extend(render_class(member))
            lines.append("")
        elif isinstance(member, Function):
            lines.extend(render_function(member, indent=""))
            lines.append("")
    while lines and lines[-1] == "":
        lines.pop()
    return lines


def build_signatures_file() -> str:
    package = griffe.load("pymediate", search_paths=[str(SRC)])
    sections = [
        "<!-- GENERATED FILE — do not hand-edit. -->",
        "<!-- Regenerate with `uv run poe context:update` (see scripts/update_context.py). -->",
        "<!-- Imported into .claude/CLAUDE.md via @context/api-signatures.md. -->",
        "",
        "# API Signatures (generated)",
        "",
        "Signatures-only blueprint of pymediate's public API. Full docstrings, guides, and"
        " examples live in `docs/content/docs/` and https://pymediate.sina-al.uk/.",
        "",
    ]
    for dotted in MODULES:
        module = package[dotted.removeprefix("pymediate.")] if dotted != "pymediate" else package
        assert isinstance(module, Module)
        body = render_module(module)
        if not body:
            continue
        sections.append(f"### `{dotted}`")
        sections.append("")
        sections.append("```python")
        sections.extend(body)
        sections.append("```")
        sections.append("")
    while sections and sections[-1] == "":
        sections.pop()
    sections.append("")
    return "\n".join(sections)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 if the generated file would change, without writing",
    )
    args = parser.parse_args()

    updated = build_signatures_file()
    current = OUTPUT.read_text() if OUTPUT.exists() else None

    if args.check:
        if current != updated:
            print(f"{OUTPUT} is stale — run `uv run poe context:update`.", file=sys.stderr)
            sys.exit(1)
        print(f"{OUTPUT} is up to date.")
        return

    if current == updated:
        print(f"{OUTPUT} already up to date.")
        return
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(updated)
    print(f"Updated {OUTPUT}.")


if __name__ == "__main__":
    main()
