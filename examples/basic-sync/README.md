# basic-sync

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/sina-al/pymediate?devcontainer_path=.devcontainer%2Fbasic-sync%2Fdevcontainer.json)

[basic](../basic/)'s task board without the event loop: the same one-file
board on `pymediate.sync`, PyMediate's synchronous mirror. Read basic first if you
haven't; this example is best enjoyed as a diff against it.

## Run it

```bash
cd examples/basic-sync
uv sync
uv run python app.py
```

```text
Created: Task(task_id=1, title='Buy groceries', done=False)
Open: Write the release notes
```

## What changed from basic

Everything imports from `pymediate.sync` instead of `pymediate`; handlers declare a
plain `def __call__`, and sending blocks — no `await`, no `asyncio.run()`. Shared
classes (`Request`, `Services`) are the *same objects* in both namespaces — only
`RequestHandler`, `Mediator`, and `PipelineBehavior` have sync variants.

```python
from pymediate.sync import Mediator, Request, RequestHandler, Services

class AddTaskHandler(RequestHandler[AddTask]):
    def __call__(self, request: AddTask) -> Task:
        ...  # create the task, return it

task = mediator.send(AddTask(title="Buy groceries"))   # still fully typed
```

This mirror keeps to the core loop — basic's `AuditTrail` trick works identically
here via `pymediate.sync.PipelineBehavior`, with `next()` in place of `await next()`.

## The files

| File | What it is |
| --- | --- |
| [`app.py`](app.py) | **Start here.** Requests, handlers, wiring, and a small demo — about 100 lines. |
| [`test_app.py`](test_app.py) | The same flows as tests: `uv run pytest` → `6 passed`. |

## Small print

- A handler's `__call__` signature is validated when the class is defined, so a
  wrongly-annotated handler — including an `async def` where a plain `def` is required —
  fails at import time, not at dispatch time.
- Handlers take their dependencies (here, a shared `TaskStore`) through plain
  constructors — no framework, no magic.

## Where next

- [adapters-sync](../adapters-sync/) — the same core pattern serving Flask, FastAPI, and
  a CLI at once.
- The docs: [quick start](https://pymediate.sina-al.uk/docs/getting-started/quick-start) ·
  [core concepts](https://pymediate.sina-al.uk/docs/getting-started/concepts).
