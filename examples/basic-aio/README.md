# basic-aio

The async mirror of [basic-sync](../basic-sync/): the same in-memory task board, built on
`pymediate.aio`.

What it shows:

- **Async handlers** — handlers subclass `pymediate.aio.Handler` and declare
  `async def __call__`, so they can await real I/O; `await mediator.send()` returns the
  response type declared by the request, exactly like the sync API.
- **Sync/async split** — only `Handler`, `Mediator`, and `PipelineBehavior` have aio
  variants; `Request` and `Services` are shared with the sync package.
- **Selective pipeline behavior** — `AuditTrail(PipelineBehavior[BoardMutation])` wraps
  dispatch as async middleware. Its type parameter selects which requests it applies to:
  the mutations (`AddTask`, `CompleteTask` subclass `BoardMutation`) are audited, the
  read-only `ListOpenTasks` is not.

Run it:

```bash
uv sync
uv run python app.py   # short demo
uv run pytest          # the tests double as the examples-contract entrypoint
```

The tests use `pytest-asyncio` in auto mode (`asyncio_mode = "auto"` in `pyproject.toml`),
so plain `async def test_*` functions just work.
