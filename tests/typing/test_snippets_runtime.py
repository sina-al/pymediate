"""Runtime execution of the valid/ snippet corpus.

"Valid" means more than "typechecks under every checker" - each valid/ snippet
must also run. This catches the failure mode type checkers can be blind to:
a snippet calling an API shape that no longer exists at runtime (per-module
suppressions once masked exactly that for a stale Services.add signature).

Convention: sync snippets execute their scenario at module level; async
snippets define `async def main()` and leave the event loop to this harness.
"""

import asyncio
import importlib.util
import inspect
import sys
from pathlib import Path

import pytest

VALID_DIR = Path(__file__).parent / "snippets" / "valid"


@pytest.mark.parametrize("snippet_file", sorted(VALID_DIR.glob("*.py")), ids=lambda p: p.stem)
def test_valid_snippet_executes(snippet_file: Path) -> None:
    """Import the snippet (running module-level code) and run main() if defined."""
    module_name = f"typing_snippet_{snippet_file.stem}"
    spec = importlib.util.spec_from_file_location(module_name, snippet_file)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
        main = getattr(module, "main", None)
        if main is not None:
            assert inspect.iscoroutinefunction(main), (
                f"{snippet_file.name} defines a non-async main() - run the scenario "
                f"at module level instead, per the corpus convention"
            )
            asyncio.run(main())
    finally:
        sys.modules.pop(module_name, None)
