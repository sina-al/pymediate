# Examples

Each directory in here is a **standalone uv project** that demonstrates PyMediate against
the released package — not against the source tree. Checked out on its own, an example is
indistinguishable from a regular downstream project: its `pyproject.toml` and `uv.lock`
point at pymediate on PyPI.

```bash
cd examples/basic-sync
uv sync
uv run pytest
```

## The examples contract

Every example must satisfy this contract — it's what lets the release pipeline discover and
run all of them with no per-example wiring (`release.yml`'s examples stage, via
`scripts/run_examples.py`):

1. **Standalone uv project**: a `pyproject.toml` at the example's root, with a committed
   `uv.lock`. Not a member of any workspace.
2. **Depends on pymediate with a loose lower bound** (e.g. `pymediate>=0.1`) so the release
   runner can re-pin it to the release candidate without a conflict. Extras are fine
   (e.g. `pymediate[di]>=0.1`): `uv add` preserves them when re-pinning, in both wheel
   and version mode — verified when `with-dependency-injector` was added.
3. **Tests included, `uv run pytest` exits 0**: pytest lives in the default (`dev`)
   dependency group, so `uv sync && uv run pytest` is the whole contract. Every example is
   also a test of the library.
4. **No `[tool.uv.sources]` or `[[tool.uv.index]]` sections**: the release runner appends
   its own (pinning pymediate to the staging index) and will refuse an example that already
   defines them.
5. **A README** explaining what the example showcases.

## How releases use these

Releases run every example twice via `scripts/run_examples.py` (see `OPERATIONS.md`):

1. **On the release PR** — `--wheel` mode: the required "Examples" check builds a wheel
   from the cut and runs each example against it, so API breakage surfaces before the
   merge (no tag, no burned version). Reproduce locally with
   `uv build && python3 scripts/run_examples.py --wheel dist/pymediate-*.whl`.
2. **After the TestPyPI publish** — `--version X.Y.Z` mode: each example is re-pinned to
   the candidate on the TestPyPI index (only pymediate resolves there — its dependencies
   still come from real PyPI) and must pass before the PyPI gate is offered.

Either way each example is copied to a temp directory first — your checkout is never
modified.
