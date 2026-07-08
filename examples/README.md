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
   runner can re-pin it to the release candidate without a conflict.
3. **Tests included, `uv run pytest` exits 0**: pytest lives in the default (`dev`)
   dependency group, so `uv sync && uv run pytest` is the whole contract. Every example is
   also a test of the library.
4. **No `[tool.uv.sources]` or `[[tool.uv.index]]` sections**: the release runner appends
   its own (pinning pymediate to the staging index) and will refuse an example that already
   defines them.
5. **A README** explaining what the example showcases.

## How releases use these

During a release (see `OPERATIONS.md`), after the candidate is published to TestPyPI,
`scripts/run_examples.py --version X.Y.Z` copies each example to a temp directory, re-pins
`pymediate==X.Y.Z` to the TestPyPI index (only pymediate resolves there — its dependencies
still come from real PyPI), and runs its tests. All examples must pass before the release
can proceed to the PyPI gate. Your checkout is never modified.
