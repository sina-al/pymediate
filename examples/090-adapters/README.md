# 090-adapters

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/sina-al/pymediate?devcontainer_path=.devcontainer%2F090-adapters%2Fdevcontainer.json)

This example exposes one task-board application through FastAPI, aiohttp, and an asyncclick
command-line interface (CLI). Each adapter translates its input into a request, sends that
request through the mediator, and translates the result. The application layer does not import
any of the three adapter frameworks.

It assumes the request and handler pattern introduced in [010-basic](../010-basic/).
It is the asynchronous twin of [090-adapters-sync](../090-adapters-sync/): the domain and
request types are equivalent, while the handlers and adapters use `async def` and `await`.

## Run

Run these commands from `examples/090-adapters`:

```bash
uv sync
uv run pytest
```

```text
18 passed
```

The tests exercise the same application through all three adapters.

## Requests, handlers, and adapters

The domain types are defined in [`src/taskboard/domain.py`](src/taskboard/domain.py). The
requests in [`src/taskboard/messages.py`](src/taskboard/messages.py) declare their result type:

```python
@dataclass
class AddTask(Request[Task]):        # "sending AddTask gives back a Task"
    title: str
```

One async handler per request, in [`src/taskboard/handlers.py`](src/taskboard/handlers.py):

```python
class AddTaskHandler(RequestHandler[AddTask]):          # from pymediate
    async def __call__(self, request: AddTask) -> Task:
        ...  # await your datastore, return the task
```

An adapter — web route, CLI command, anything — then only ever does one thing: build a
request object and await it.

```python
task = await mediator.send(AddTask(title="Buy milk"))   # typed: task is a Task
```

Nothing under `domain.py`, `messages.py`, `handlers.py`, or `wiring.py` imports FastAPI,
aiohttp, or asyncclick. All three adapters can therefore use the same application layer.

## Read the code

In suggested reading order:

| File | What to read |
| --- | --- |
| [`src/taskboard/domain.py`](src/taskboard/domain.py) | **Start here.** `Task`, `TaskStore`, `TaskNotFoundError` — no request, no handler, no framework. |
| [`src/taskboard/messages.py`](src/taskboard/messages.py) | The requests: `AddTask`, `CompleteTask`, `ListOpenTasks`. |
| [`src/taskboard/handlers.py`](src/taskboard/handlers.py) | One async handler per request — the framework-free application logic. |
| [`src/taskboard/wiring.py`](src/taskboard/wiring.py) | `build_mediator` — the one place that assembles domain, messages, and handlers. |
| [`src/taskboard/adapters/cli.py`](src/taskboard/adapters/cli.py) | The command-line adapter: asyncclick commands await the mediator directly. |
| [`src/taskboard/adapters/fastapi.py`](src/taskboard/adapters/fastapi.py) | `async def` endpoints — diff it against the sync example's version: only `async`/`await` changed. |
| [`src/taskboard/adapters/aiohttp.py`](src/taskboard/adapters/aiohttp.py) | A third dialect: plain handler functions, mediator carried on the app, errors mapped in a middleware. |
| [`tests/`](tests/) | One suite per adapter — together they cover the application three times over. |

## Details

### Try each adapter

**CLI** — commands chain, so one invocation runs a whole session:

```bash
uv run taskboard add "Buy milk" add "Ship it" complete 1 list
```

```text
Added task 1: Buy milk
Added task 2: Ship it
Completed task 1: Buy milk
[2] Ship it
```

**FastAPI** (<http://127.0.0.1:8000> — interactive docs at `/docs`):

```bash
uv run uvicorn taskboard.adapters.fastapi:app
```

**aiohttp** (<http://127.0.0.1:8080>):

```bash
uv run python -m taskboard.adapters.aiohttp
```

In another terminal, send the same request to either server. Use port 8000 for FastAPI or
8080 for aiohttp:

```bash
BASE_URL=http://127.0.0.1:8000  # change to :8080 for aiohttp
curl -X POST "$BASE_URL/tasks" -H 'content-type: application/json' -d '{"title": "Buy milk"}'
```

```json
{"task_id": 1, "title": "Buy milk", "done": false}
```

### Notes

- Each adapter translates `TaskNotFoundError` into its own error response. FastAPI and aiohttp
  return HTTP 404. The CLI prints `Error: No task with id 999` and exits with status 1 for
  `uv run taskboard complete 999`.
- Everything imports from the top-level `pymediate` — the async API. Only
  `RequestHandler`, `Mediator`, and `PipelineBehavior` have sync variants
  (`pymediate.sync`); `Request` and `Services` are the same objects on both sides.
- The tests use each framework's own async tooling: httpx2 over ASGI for FastAPI,
  pytest-aiohttp's `aiohttp_client` for aiohttp, and asyncclick's `CliRunner` — all under
  pytest-asyncio's auto mode, so test functions are plain `async def`.
- The store is in memory, so every app instance and every CLI invocation starts empty.

## Where next

- [100-dependency-injection](../100-dependency-injection/) — configure shared, per-use, and
  context-local dependencies.
- [090-adapters-sync](../090-adapters-sync/) — use the same application with Flask, FastAPI
  `def` routes, and click.
- [010-basic](../010-basic/) — review the core async pattern without framework adapters.
- The docs: [quick start](https://pymediate.sina-al.uk/docs/getting-started/quick-start) ·
  [core concepts](https://pymediate.sina-al.uk/docs/getting-started/concepts) for the
  ideas this example leans on.
