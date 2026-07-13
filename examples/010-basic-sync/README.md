# 010-basic-sync

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/sina-al/pymediate?devcontainer_path=.devcontainer%2F010-basic-sync%2Fdevcontainer.json)

[010-basic](../010-basic/)'s `send()` loop without the event loop: the same one-file round
trip on `pymediate.sync`, PyMediate's synchronous mirror. Read 010-basic first if you
haven't; this example is best enjoyed as a diff against it.

## Run it

```bash
cd examples/010-basic-sync
uv sync
uv run python app.py
```

```text
Created: Task(task_id=1, title='Buy groceries', done=False)
Assigned id: 1
```

## What changed from 010-basic

Everything imports from `pymediate.sync` instead of `pymediate`; the handler declares a
plain `def __call__`, and sending blocks — no `await`, no `asyncio.run()`. `Request` and
`Services` are the *same objects* in both namespaces — only `RequestHandler` and `Mediator`
have sync variants. The typing win is identical: the response type flows to the call site
with zero casts.

```python
from pymediate.sync import Mediator, Request, RequestHandler, Services

class AddTaskHandler(RequestHandler[AddTask]):
    def __call__(self, request: AddTask) -> Task:
        ...                       # store the task, return it

task = mediator.send(AddTask(title="Buy groceries"))   # inferred as Task, no await
assert task.task_id == 1                                # typed attribute access
```

## The files

| File | What it is |
| --- | --- |
| [`app.py`](app.py) | **Start here.** One request, one handler, the wiring, and a tiny demo. |
| [`test_app.py`](test_app.py) | The same round trip as tests: `uv run pytest` → `3 passed`. |

## Small print

- A handler's `__call__` signature is validated when the class is defined, so a
  wrongly-annotated handler — including an `async def` where a plain `def` is required —
  fails at import time, not at dispatch time.
- The handler takes its dependency (here, a shared `TaskStore`) through a plain
  constructor — no framework, no magic.

## Where next

- [010-basic](../010-basic/) — the async original this mirrors, on the top-level
  `pymediate` API.
- The docs: [quick start](https://pymediate.sina-al.uk/docs/getting-started/quick-start) ·
  [core concepts](https://pymediate.sina-al.uk/docs/getting-started/concepts).
