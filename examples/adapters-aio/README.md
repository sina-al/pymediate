# adapters-aio

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/sina-al/pymediate?devcontainer_path=.devcontainer%2Fadapters-aio%2Fdevcontainer.json)

One small task-board application, written once — then delivered through **FastAPI**,
**aiohttp**, and an **asyncclick CLI** without changing a line of it. It's the async twin
of [adapters-sync](../adapters-sync/): same domain, same shape, `async def` end to end.

## Run it

```bash
cd examples/adapters-aio
uv sync
uv run pytest
```

```text
18 passed
```

That one test run just drove the same application through all three adapters.

## The idea, in ten lines

The whole application lives in [`src/taskboard/core.py`](src/taskboard/core.py). It
defines requests — each declaring what it responds with — and one async handler per
request:

```python
@dataclass
class AddTask(Request[Task]):        # "sending AddTask gives back a Task"
    title: str

class AddTaskHandler(Handler[AddTask]):          # from pymediate.aio
    async def __call__(self, request: AddTask) -> Task:
        ...  # await your datastore, return the task
```

An adapter — web route, CLI command, anything — then only ever does one thing: build a
request object and await it.

```python
task = await mediator.send(AddTask(title="Buy milk"))   # typed: task is a Task
```

`core.py` imports pymediate and the standard library, nothing else. FastAPI, aiohttp, and
asyncclick never appear in it — which is exactly why all three can share it.

## The files

In suggested reading order:

| File | What it is |
| --- | --- |
| [`src/taskboard/core.py`](src/taskboard/core.py) | **Start here.** The entire application: requests, async handlers, wiring. |
| [`src/taskboard/adapters/cli.py`](src/taskboard/adapters/cli.py) | The smallest adapter: asyncclick commands await the mediator directly. |
| [`src/taskboard/adapters/fastapi_app.py`](src/taskboard/adapters/fastapi_app.py) | `async def` endpoints — diff it against the sync example's version: only `async`/`await` changed. |
| [`src/taskboard/adapters/aiohttp_app.py`](src/taskboard/adapters/aiohttp_app.py) | A third dialect: plain handler functions, mediator carried on the app, errors mapped in a middleware. |
| [`tests/`](tests/) | One suite per adapter — together they cover the core three times over. |

## Try each adapter

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
uv run uvicorn taskboard.adapters.fastapi_app:app
```

**aiohttp** (<http://127.0.0.1:8080>):

```bash
uv run python -m taskboard.adapters.aiohttp_app
```

Same requests against either server:

```bash
curl -X POST localhost:8080/tasks -H 'content-type: application/json' -d '{"title": "Buy milk"}'
```

```json
{"task_id": 1, "title": "Buy milk", "done": false}
```

## Small print

- Each adapter also translates the core's one domain error its own way:
  `TaskNotFoundError` becomes HTTP **404** in FastAPI (`@app.exception_handler`) and
  aiohttp (a middleware), and **exit code 1** with a message on stderr in the CLI
  (`ClickException`). Try it: `uv run taskboard complete 999`.
- Only `Handler`, `Mediator`, and `PipelineBehavior` have async variants
  (`pymediate.aio`); `Request` and `Services` are shared with the sync package.
- The tests use each framework's own async tooling: httpx2 over ASGI for FastAPI,
  pytest-aiohttp's `aiohttp_client` for aiohttp, and asyncclick's `CliRunner` — all under
  pytest-asyncio's auto mode, so test functions are plain `async def`.
- The store is in memory, so every app instance and every CLI invocation starts empty.

## Where next

- [adapters-sync](../adapters-sync/) — this example's sync twin (Flask, FastAPI `def`,
  click).
- [basic-aio](../basic-aio/) — the async core pattern at its smallest, plus a pipeline
  behavior.
- The docs: [quick start](https://pymediate.sina-al.uk/docs/getting-started/quick-start) ·
  [core concepts](https://pymediate.sina-al.uk/docs/getting-started/concepts) for the
  ideas this example leans on.
