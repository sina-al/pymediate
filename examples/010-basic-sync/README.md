# 010-basic-sync

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/sina-al/pymediate?devcontainer_path=.devcontainer%2F010-basic-sync%2Fdevcontainer.json)

This is the first synchronous implementation lesson. It shows the complete `send()` path
in one file using `pymediate.sync`: define a request and its response type, implement a
handler, register it, and send the request.

## Run

From this example directory:

```bash
uv sync
uv run python app.py
```

```text
Created: Task(task_id=1, title='Buy groceries', done=False)
Assigned id: 1
```

## Send a request synchronously

Everything imports from `pymediate.sync` instead of `pymediate`; the handler declares a
plain `def __call__`, and sending blocks — no `await`, no `asyncio.run()`. `Request` and
`Services` are the *same objects* in both namespaces — only `RequestHandler` and `Mediator`
have synchronous variants. `AddTask(Request[Task])` determines the return type of
`mediator.send(AddTask(...))`, while the handler's `-> Task` annotation checks the handler
implementation.

```python
from pymediate.sync import Mediator, Request, RequestHandler, Services

class AddTaskHandler(RequestHandler[AddTask]):
    def __call__(self, request: AddTask) -> Task:
        ...                       # store the task, return it

task = mediator.send(AddTask(title="Buy groceries"))   # inferred as Task, no await
assert task.task_id == 1                                # typed attribute access
```

## Read the code

| File | What to read |
| --- | --- |
| [`app.py`](app.py) | **Start here.** One request, one handler, the wiring, and a demo. |
| [`test_app.py`](test_app.py) | The same round trip as tests: `uv run pytest` → `3 passed`. |

## Details

- A handler's `__call__` signature is validated when the class is defined, so a
  wrongly-annotated handler — including an `async def` where a plain `def` is required —
  fails at import time, not at dispatch time.
- The handler receives its `TaskStore` dependency through its constructor.

## Where next

- [020-events-sync](../020-events-sync/) — publish one event to several handlers
  synchronously.
- [010-basic](../010-basic/) — the asynchronous version on the top-level `pymediate` API.
- The docs: [quick start](https://pymediate.sina-al.uk/docs/getting-started/quick-start) ·
  [core concepts](https://pymediate.sina-al.uk/docs/getting-started/concepts).
