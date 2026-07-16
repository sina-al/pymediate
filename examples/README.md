# Examples

Every directory here is a small, complete application built on
[PyMediate](https://github.com/sina-al/pymediate) — self-contained, tested, and runnable
in about a minute. You don't need to have read the documentation first: each README
starts from zero.

```bash
cd examples/005-why-a-mediator   # or any other example
uv sync
uv run pytest
```

Prefer zero setup? Every example README has an **Open in GitHub Codespaces** badge that
launches it in a browser IDE, dependencies already installed.

## The examples

In suggested order:

| # | Example | What it shows |
| --- | --- | --- |
| 1 | [005-why-a-mediator](005-why-a-mediator/) | **Start here.** Why not just one big service? The same orders feature as a god class — shown failing four concrete ways — then as pymediate handlers, each failure gone. |
| 2 | [005-why-a-mediator-sync](005-why-a-mediator-sync/) | The same before→after contrast on `pymediate.sync`, no event loop. |
| 3 | [010-basic](010-basic/) | The whole `send()` loop in one file: a typed request, one `async def` handler, `await mediator.send()`, a typed response — zero casts. |
| 4 | [010-basic-sync](010-basic-sync/) | The same `send()` round-trip without the event loop, on `pymediate.sync`. |
| 5 | [020-events](020-events/) | `await mediator.publish()` fans one event out to many independent subscribers, delivered **concurrently** — plus a zero-subscriber no-op. |
| 6 | [020-events-sync](020-events-sync/) | The same fan-out on `pymediate.sync`, delivered **sequentially** — diff it against #5. |
| 7 | [030-streaming](030-streaming/) | `mediator.stream()`: one request answered by a lazy feed of typed chunks (`AsyncIterator`) — resolved eagerly, iterated lazily. |
| 8 | [030-streaming-sync](030-streaming-sync/) | The same lazy stream on `pymediate.sync` (`Iterator`). |
| 9 | [040-pipeline-behaviors](040-pipeline-behaviors/) | Cross-cutting concerns (logging, auth, caching, transactions) as one ordered `PipelineBehavior` stack, routed by the type parameter; a cache hit short-circuits the handler. |
| 10 | [040-pipeline-behaviors-sync](040-pipeline-behaviors-sync/) | The same stack on `pymediate.sync`. |
| 11 | [045-behaviors-vs-decorators](045-behaviors-vs-decorators/) | Why not just a decorator? The same rate limit as a decorator (dependency bound at import time) vs. a behavior (dependency injected) — the decorator can't cleanly swap it, the behavior can. |
| 12 | [045-behaviors-vs-decorators-sync](045-behaviors-vs-decorators-sync/) | The same contrast on `pymediate.sync`, no event loop. |
| 13 | [060-messages](060-messages/) | Requests as immutable **value objects**: a `frozen` request that doubles as its own cache key, a secret hidden from logs, and `__post_init__` validation that rejects bad data at construction. |
| 14 | [060-messages-sync](060-messages-sync/) | The same message design on `pymediate.sync`. |
| 15 | [090-adapters](090-adapters/) | One framework-free async core delivered through FastAPI, aiohttp, **and** an async CLI, unchanged. |
| 16 | [090-adapters-sync](090-adapters-sync/) | The sync twin of #15: Flask, FastAPI, and a click CLI over one sync core. |
| 17 | [with-dependency-injector](with-dependency-injector/) | Swap hand-wiring for a real DI container — PyMediate's optional `di` extra. |

1–2 make the case for a mediator at all; 3–4 teach `send` (request → response); 5–6 add
`publish` (event fan-out); 7–8 add `stream` (a lazy feed of typed chunks); 9–10 wrap
requests with pipeline behaviors; 11–12 contrast a behavior with a plain decorator; 13–14
design requests as value objects; 15–16 make the framework-independence argument; 17
plugs it into a DI container. Async and sync
examples mirror each other deliberately — diffing a pair is the fastest way to see how
small the sync delta is. (`with-dependency-injector` keeps its original name for now;
it's renumbered later as the
[examples-curriculum epic](https://github.com/sina-al/pymediate/issues/74) proceeds.)

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
