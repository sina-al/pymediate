# 090-adapters-sync

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/sina-al/pymediate?devcontainer_path=.devcontainer%2F090-adapters-sync%2Fdevcontainer.json)

One small task-board application, written once — then delivered through **Flask**,
**FastAPI**, and a **click CLI** without changing a line of it. That's the point of this
example: with PyMediate, your application logic doesn't know or care which framework is
driving it.

## Run it

```bash
cd examples/090-adapters-sync
uv sync
uv run pytest
```

```text
18 passed
```

That one test run just drove the same application through all three adapters.

## The idea, in ten lines

The domain lives in [`src/taskboard/domain.py`](src/taskboard/domain.py) and
[`src/taskboard/messages.py`](src/taskboard/messages.py) — requests, each declaring what
it responds with:

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
FastAPI, or click — which is exactly why all three can share it.

## The files

In suggested reading order:

| File | What it is |
| --- | --- |
| [`src/taskboard/domain.py`](src/taskboard/domain.py) | **Start here.** `Task`, `TaskStore`, `TaskNotFoundError` — no request, no handler, no framework. |
| [`src/taskboard/messages.py`](src/taskboard/messages.py) | The requests: `AddTask`, `CompleteTask`, `ListOpenTasks`. |
| [`src/taskboard/handlers.py`](src/taskboard/handlers.py) | One handler per request — the framework-free application logic. |
| [`src/taskboard/wiring.py`](src/taskboard/wiring.py) | `build_mediator` — the one place that assembles domain, messages, and handlers. |
| [`src/taskboard/adapters/cli.py`](src/taskboard/adapters/cli.py) | The smallest adapter: click commands → requests. |
| [`src/taskboard/adapters/flask.py`](src/taskboard/adapters/flask.py) | Flask routes → requests; JSON in and out. |
| [`src/taskboard/adapters/fastapi.py`](src/taskboard/adapters/fastapi.py) | The same routes on FastAPI; the domain's `Task` dataclass doubles as the response model. |
| [`tests/`](tests/) | One suite per adapter — together they cover the application three times over. |

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

**Flask** (<http://127.0.0.1:5000>):

```bash
uv run flask --app taskboard.adapters.flask run
```

**FastAPI** (<http://127.0.0.1:8000> — interactive docs at `/docs`):

```bash
uv run uvicorn taskboard.adapters.fastapi:app
```

Same requests against either server:

```bash
curl -X POST localhost:8000/tasks -H 'content-type: application/json' -d '{"title": "Buy milk"}'
```

```json
{"task_id": 1, "title": "Buy milk", "done": false}
```

## Small print

- Each adapter also translates the domain's one error its own way: `TaskNotFoundError`
  becomes HTTP **404** in Flask (`@app.errorhandler`) and FastAPI
  (`@app.exception_handler`), and **exit code 1** with a message on stderr in the CLI
  (`ClickException`). Try it: `uv run taskboard complete 999`.
- The FastAPI endpoints here are plain `def` functions because the domain is synchronous
  (FastAPI runs them in a threadpool). The async mirror of this whole example —
  same domain, `async def` end to end — is [090-adapters](../090-adapters/).
- The store is in memory, so every app instance and every CLI invocation starts empty.
  The tests lean on that for isolation.

## Where next

- [090-adapters](../090-adapters/) — this example's async twin (FastAPI `async def`,
  aiohttp, asyncclick).
- [010-basic-sync](../010-basic-sync/) — the same core pattern at its smallest, if this
  felt like too much at once.
- The docs: [quick start](https://pymediate.sina-al.uk/docs/getting-started/quick-start) ·
  [core concepts](https://pymediate.sina-al.uk/docs/getting-started/concepts) for the
  ideas this example leans on.
