# adapters-sync

Framework independence, demonstrated: one synchronous PyMediate core behind three
different delivery mechanisms. The async mirror is
[adapters-aio](../adapters-aio/).

- **`core.py`** — the entire application: requests, handlers, wiring. Imports pymediate
  and the standard library, nothing else. No adapter concern ever appears here.
- **`flask_app.py`** — Flask adapter: routes + JSON, `TaskNotFoundError` → 404 via
  `@app.errorhandler`.
- **`fastapi_app.py`** — FastAPI adapter with plain `def` endpoints (FastAPI threadpools
  them): the core's `Task` dataclass doubles as the response model,
  `TaskNotFoundError` → 404 via `@app.exception_handler`.
- **`cli.py`** — click adapter: a chained command group, `TaskNotFoundError` →
  stderr + exit code 1 via `ClickException`.

Each adapter is a thin translation layer: framework input → request object →
`mediator.send()` → framework output. That's why the tests only exercise the adapters
(`test_flask_app.py`, `test_fastapi_app.py`, `test_cli.py`) — each suite drives the full
core through its framework's own test tooling, so the core is covered three times over
without a single direct core test.

Run it:

```bash
uv sync
uv run pytest                                # all three adapters' tests

# CLI — commands chain, so one invocation runs a whole session against one store:
uv run python cli.py add "Buy milk" add "Ship it" complete 1 list

# Flask (http://127.0.0.1:5000):
uv run flask --app flask_app run

# FastAPI (http://127.0.0.1:8000, interactive docs at /docs):
uv run uvicorn fastapi_app:app
```

Try the HTTP adapters with curl (same requests, either port):

```bash
curl -X POST localhost:8000/tasks -H 'content-type: application/json' -d '{"title": "Buy milk"}'
curl -X POST localhost:8000/tasks/1/complete
curl localhost:8000/tasks
```
