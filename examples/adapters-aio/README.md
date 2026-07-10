# adapters-aio

Framework independence, demonstrated: one asynchronous PyMediate core behind three
different delivery mechanisms. The sync mirror is [adapters-sync](../adapters-sync/).

- **`core.py`** — the entire application: requests, `async def` handlers on
  `pymediate.aio`, wiring. Imports pymediate and the standard library, nothing else.
- **`fastapi_app.py`** — FastAPI adapter with `async def` endpoints. Diff it against the
  sync example's `fastapi_app.py`: same framework, same routes — only `async`/`await`
  changed.
- **`aiohttp_app.py`** — aiohttp adapter: plain handler functions, the mediator carried
  on the application via `web.AppKey`, `TaskNotFoundError` → 404 via a middleware.
- **`cli.py`** — asyncclick adapter: click's async fork runs the event loop, so commands
  are `async def` and await the mediator directly. `TaskNotFoundError` → stderr + exit
  code 1 via `ClickException`.

Each adapter is a thin translation layer: framework input → request object →
`await mediator.send()` → framework output. That's why the tests only exercise the
adapters (`test_fastapi_app.py`, `test_aiohttp_app.py`, `test_cli.py`) — each suite
drives the full core through its framework's own async test tooling (httpx over ASGI,
pytest-aiohttp's `aiohttp_client`, asyncclick's `CliRunner`), so the core is covered
three times over without a single direct core test.

Run it:

```bash
uv sync
uv run pytest                                # all three adapters' tests

# CLI — commands chain, so one invocation runs a whole session against one store:
uv run python cli.py add "Buy milk" add "Ship it" complete 1 list

# FastAPI (http://127.0.0.1:8000, interactive docs at /docs):
uv run uvicorn fastapi_app:app

# aiohttp (http://0.0.0.0:8080):
uv run python aiohttp_app.py
```

Try the HTTP adapters with curl (same requests, either port):

```bash
curl -X POST localhost:8080/tasks -H 'content-type: application/json' -d '{"title": "Buy milk"}'
curl -X POST localhost:8080/tasks/1/complete
curl localhost:8080/tasks
```
