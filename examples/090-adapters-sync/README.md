# 090-adapters-sync

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/sina-al/pymediate?devcontainer_path=.devcontainer%2F090-adapters-sync%2Fdevcontainer.json)

This example exposes one task-board application through Flask, FastAPI, and a click
command-line interface (CLI). Each adapter translates its input into a request, sends that
request through the mediator, and translates the result. The application layer does not import
any of the three adapter frameworks.

It assumes the request and handler pattern introduced in
[010-basic-sync](../010-basic-sync/).

## Run

Run these commands from `examples/090-adapters-sync`:

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

One handler per request, in [`src/taskboard/handlers.py`](src/taskboard/handlers.py):

```python
class AddTaskHandler(RequestHandler[AddTask]):          # from pymediate.sync
    def __call__(self, request: AddTask) -> Task:
        ...  # create the task, return it
```

An adapter — web route, CLI command, anything — then only ever does one thing: build a
request object and send it.

```python
task = mediator.send(AddTask(title="Buy milk"))   # typed: your IDE knows task is a Task
```

Nothing under `domain.py`, `messages.py`, `handlers.py`, or `wiring.py` imports Flask,
FastAPI, or click. All three adapters can therefore use the same application layer.

## Read the code

In suggested reading order:

| File | What to read |
| --- | --- |
| [`src/taskboard/domain.py`](src/taskboard/domain.py) | **Start here.** `Task`, `TaskStore`, `TaskNotFoundError` — no request, no handler, no framework. |
| [`src/taskboard/messages.py`](src/taskboard/messages.py) | The requests: `AddTask`, `CompleteTask`, `ListOpenTasks`. |
| [`src/taskboard/handlers.py`](src/taskboard/handlers.py) | One handler per request — the framework-free application logic. |
| [`src/taskboard/wiring.py`](src/taskboard/wiring.py) | `build_mediator` — the one place that assembles domain, messages, and handlers. |
| [`src/taskboard/adapters/cli.py`](src/taskboard/adapters/cli.py) | The command-line adapter: click commands create and send requests. |
| [`src/taskboard/adapters/flask.py`](src/taskboard/adapters/flask.py) | Flask routes → requests; JSON in and out. |
| [`src/taskboard/adapters/fastapi.py`](src/taskboard/adapters/fastapi.py) | The same routes on FastAPI; the domain's `Task` dataclass doubles as the response model. |
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

**Flask** (<http://127.0.0.1:5000>):

```bash
uv run flask --app taskboard.adapters.flask run
```

**FastAPI** (<http://127.0.0.1:8000> — interactive docs at `/docs`):

```bash
uv run uvicorn taskboard.adapters.fastapi:app
```

In another terminal, send the same request to either server. Use port 5000 for Flask or 8000
for FastAPI:

```bash
BASE_URL=http://127.0.0.1:5000  # change to :8000 for FastAPI
curl -X POST "$BASE_URL/tasks" -H 'content-type: application/json' -d '{"title": "Buy milk"}'
```

```json
{"task_id": 1, "title": "Buy milk", "done": false}
```

### Notes

- Each adapter translates `TaskNotFoundError` into its own error response. Flask and FastAPI
  return HTTP 404. The CLI prints `Error: No task with id 999` and exits with status 1 for
  `uv run taskboard complete 999`.
- The FastAPI endpoints here are plain `def` functions because the domain is synchronous
  (FastAPI runs them in a threadpool). The async mirror of this whole example —
  same domain, `async def` end to end — is [090-adapters](../090-adapters/).
- The store is in memory, so every app instance and every CLI invocation starts empty.
  The tests lean on that for isolation.

## Where next

- [100-dependency-injection-sync](../100-dependency-injection-sync/) — configure shared,
  per-use, and context-local dependencies.
- [090-adapters](../090-adapters/) — use the same application with FastAPI `async def`
  routes, aiohttp, and asyncclick.
- [010-basic-sync](../010-basic-sync/) — review the core sync pattern without adapters.
- The docs: [quick start](https://pymediate.sina-al.uk/docs/getting-started/quick-start) ·
  [core concepts](https://pymediate.sina-al.uk/docs/getting-started/concepts) for the
  ideas this example leans on.
