# 100-dependency-injection-sync

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/sina-al/pymediate?devcontainer_path=.devcontainer%2F100-dependency-injection-sync%2Fdevcontainer.json)

The synchronous mirror of [100-dependency-injection](../100-dependency-injection/), on
`pymediate.sync`. Same container, same three provider lifetimes — **Factory** (rebuilt
per dispatch), **Singleton** (app-wide), and **`ContextLocalSingleton`** (one instance
per logical scope) — resolved **by type, not by provider name**, via PyMediate's
optional **`di` extra**.

## Run it

```bash
cd examples/100-dependency-injection-sync
uv sync
uv run python app.py
```

```text
Registered: User(user_id=1, username='alice')
Unit of work: ['begin', "registered 'alice'", 'commit']
Registered: User(user_id=2, username='bob')
Unit of work: ['begin', "registered 'bob'", 'commit']
```

## What changes from the async version

Only the API import and the mechanics — the container and the three lifetimes are
identical:

```python
# app.py
from pymediate.sync import Mediator, Next, PipelineBehavior, Request, RequestHandler

class TransactionLoggingBehavior(PipelineBehavior[Request]):
    def __call__(self, request, next):        # no async
        self._unit_of_work.record("begin")
        response = next()                      # no await
        self._unit_of_work.record("commit")
        return response
```

`AppContainer` — `Singleton` repository, `ContextLocalSingleton` unit of work, `Factory`
handlers and behavior — is byte-for-byte the same declaration as the async twin.

## The files

| File | What it is |
| --- | --- |
| [`app.py`](app.py) | **Start here.** A small user directory: requests, handlers, the unit of work, and the container. |
| [`test_app.py`](test_app.py) | Dispatch plus all three lifetimes, as tests: `uv run pytest` → `7 passed`. |

## Small print

- This example depends on `pymediate[di]`, which pulls in `dependency-injector`. The
  integration lives in `pymediate.providers` — the core package never imports it.
- `DependencyInjectorServiceProvider` scans the container once, at construction. Build it
  from a finished container, not from a provider inside that same container.

## Where next

- [100-dependency-injection](../100-dependency-injection/) — the async default, with the
  full explanation of all three lifetimes.
- [090-adapters-sync](../090-adapters-sync/) — a bigger composition-root story: one core,
  three frameworks.
- The docs: [dependency injection](https://pymediate.sina-al.uk/docs/guide/dependency-injection) ·
  [quick start](https://pymediate.sina-al.uk/docs/getting-started/quick-start).
