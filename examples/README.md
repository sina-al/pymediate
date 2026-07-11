# Examples

Every directory here is a small, complete application built on
[PyMediate](https://github.com/sina-al/pymediate) — self-contained, tested, and runnable
in about a minute. You don't need to have read the documentation first: each README
starts from zero.

```bash
cd examples/basic-async   # or any other example
uv sync
uv run pytest
```

Prefer zero setup? Every example README has an **Open in GitHub Codespaces** badge that
launches it in a browser IDE, dependencies already installed.

## The examples

In suggested order:

| # | Example | What it shows |
| --- | --- | --- |
| 1 | [basic-async](basic-async/) | **Start here.** The whole pattern in one file: typed requests, one `async def` handler each, `await mediator.send()`, plus a pipeline behavior auditing every mutation. |
| 2 | [basic-sync](basic-sync/) | The same board without the event loop, on `pymediate.sync` — PyMediate's synchronous mirror. |
| 3 | [events-async](events-async/) | The mediator's other half: `await mediator.publish()` fans one event out to many independent handlers. |
| 4 | [with-dependency-injector](with-dependency-injector/) | Swap hand-wiring for a real DI container — PyMediate's optional `di` extra. |
| 5 | [adapters-async](adapters-async/) | One framework-free async core delivered through FastAPI, aiohttp, **and** an async CLI, unchanged. |
| 6 | [adapters-sync](adapters-sync/) | The sync twin of #5: Flask, FastAPI, and a click CLI over one sync core. |

1–2 teach `send` (request → response), 3 adds `publish` (event fan-out), 4 plugs it into a
container, 5–6 make the framework-independence argument. Async and sync examples mirror
each other deliberately — diffing a pair is the fastest way to see how small the sync delta
is.

## The examples contract

Every example must satisfy this contract — it's what lets the release pipeline discover
and run all of them with no per-example wiring (`release.yml`'s examples stage, via
`scripts/run_examples.py`):

1. **Standalone uv project**: a `pyproject.toml` at the example's root, with a committed
   `uv.lock`. Not a member of any workspace.
2. **Depends on pymediate with a loose lower bound** (e.g. `pymediate>=0.5`) so the release
   runner can re-pin it to the release candidate without a conflict. Extras are fine
   (e.g. `pymediate[di]>=0.5`): `uv add` preserves them when re-pinning, in both wheel
   and version mode — verified when `with-dependency-injector` was added.
3. **Tests included, `uv run pytest` exits 0**: pytest lives in the default (`dev`)
   dependency group, so `uv sync && uv run pytest` is the whole contract. Every example is
   also a test of the library.
4. **No `[tool.uv.sources]` or `[[tool.uv.index]]` sections**: the release runner appends
   its own (pinning pymediate to the staging index) and will refuse an example that already
   defines them.
5. **A README** explaining what the example showcases.

Beyond the contract, examples in this repo are held to a deliberate quality bar —
structure, README shape, IDE config, devcontainer, and verification are all specified in
`.claude/skills/example/SKILL.md`. Use that skill when adding or changing an example.

## How releases use these

The examples are the release pipeline's proxy downstream users: they consume pymediate
from an index like any real project, so they can verify what the library's own test suite
can't — the built, published artifact. Releases run every example **four times** via
`scripts/run_examples.py` (see `OPERATIONS.md` for the full rationale, and ADR 0007 for
the design decision):

1. **On the release PR** — `--wheel` mode: the required "Examples" check builds a wheel
   from the cut and runs each example against it, so API breakage surfaces before the
   merge (no tag, no burned version). Reproduce locally with
   `uv build && python3 scripts/run_examples.py --wheel dist/pymediate-*.whl`.
2. **In `release.yml`, before publishing anywhere** — `--wheel` mode again, against the
   release-versioned artifact and freshly resolved dependencies, so drift since the PR
   check fails before a version number burns.
3. **After the TestPyPI publish** — `--version X.Y.Z` mode: each example is re-pinned to
   the candidate on the TestPyPI index (only pymediate resolves there — its dependencies
   still come from real PyPI) and must pass before the PyPI gate is offered.
4. **After the PyPI publish** — `--version X.Y.Z` mode against `pypi.org`: a smoke test
   of the exact artifact users install, gating the GitHub Release.

Either way each example is copied to a temp directory first — your checkout is never
modified.
