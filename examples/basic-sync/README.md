# basic-sync

The smallest useful PyMediate application: an in-memory task board using the synchronous
API.

What it shows:

- **Typed requests** — `AddTask(Request[Task])` declares that sending it yields a `Task`;
  `ListOpenTasks(Request[list[Task]])` yields a list. `mediator.send()` returns the right
  type, checked by mypy and validated at runtime.
- **One handler per request** — `Handler[AddTask]` subclasses validate their `__call__`
  signature at class-definition time, so a wrongly-annotated handler fails at import, not
  at dispatch.
- **Plain-object wiring** — handlers take their dependencies (here a `TaskStore`) through
  ordinary constructors; `Services` + `Mediator` do the routing, nothing else.

Run it:

```bash
uv sync
uv run python app.py   # short demo
uv run pytest          # the tests double as the examples-contract entrypoint
```
