# Examples

Every directory here is a small, complete application built on
[PyMediate](https://github.com/sina-al/pymediate) — self-contained, tested, and runnable
in about a minute. You don't need to have read the documentation first: each README
starts from zero.

```bash
cd examples/basic-sync   # or any other example
uv sync
uv run pytest
```

Prefer zero setup? Every example README has an **Open in GitHub Codespaces** badge that
launches it in a browser IDE, dependencies already installed.

## The examples

In suggested order:

| # | Example | What it shows |
| --- | --- | --- |
| 1 | [basic-sync](basic-sync/) | **Start here.** The whole pattern in one file: typed requests, one handler each, `mediator.send()`. |
| 2 | [basic-aio](basic-aio/) | The same board with `async def` handlers, plus a pipeline behavior auditing every mutation. |
| 3 | [with-dependency-injector](with-dependency-injector/) | Swap hand-wiring for a real DI container — PyMediate's optional `di` extra. |
| 4 | [adapters-sync](adapters-sync/) | One framework-free core delivered through Flask, FastAPI, **and** a CLI, unchanged. |
| 5 | [adapters-aio](adapters-aio/) | The async twin of #4: FastAPI, aiohttp, and an async CLI over one async core. |
| 6 | [hexagonal-architecture](hexagonal-architecture/) | The kitchen sink: a uv workspace where the core owns its interfaces and Postgres, Neo4j, Redis, and the web are plug-in packages — with Docker images per variant. |

1–2 teach the pattern, 3 plugs it into a container, 4–5 make the framework-independence
argument, and 6 scales it to a full application with swappable infrastructure. Sync and
async examples mirror each other deliberately — diffing a pair is the fastest way to see
how small the async delta is.

## The examples contract

Every example must satisfy this contract — it's what lets the release pipeline discover
and run all of them with no per-example wiring (`release.yml`'s examples stage, via
`scripts/run_examples.py`):

1. **Standalone uv project**: a `pyproject.toml` at the example's root, with a committed
   `uv.lock`. Not a member of any *outside* workspace — an example may itself **be** a uv
   workspace (see `hexagonal-architecture/`), as long as its root satisfies the rest of
   the contract.
2. **Depends on pymediate with a loose lower bound** (e.g. `pymediate>=0.1`) so the release
   runner can re-pin it to the release candidate without a conflict. Extras are fine
   (e.g. `pymediate[di]>=0.1`): `uv add` preserves them when re-pinning, in both wheel
   and version mode — verified when `with-dependency-injector` was added.
3. **Tests included, `uv run pytest` exits 0**: pytest lives in the default (`dev`)
   dependency group, so `uv sync && uv run pytest` is the whole contract. Every example is
   also a test of the library.
4. **No `[[tool.uv.index]]` sections, and no `[tool.uv.sources]` entries other than
   `{ workspace = true }`**: the release runner adds its own index and source (pinning
   pymediate to the staging index, merging into an existing sources table if a workspace
   example has one) and will refuse an example that defines anything else — a path, git,
   or index source would fight the release re-pin.
5. **A README** explaining what the example showcases.

Beyond the contract, examples in this repo are held to a deliberate quality bar —
structure, README shape, IDE config, devcontainer, and verification are all specified in
`.claude/skills/example/SKILL.md`. Use that skill when adding or changing an example.

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
