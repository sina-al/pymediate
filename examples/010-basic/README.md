# 010-basic

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/sina-al/pymediate?devcontainer_path=.devcontainer%2F010-basic%2Fdevcontainer.json)

This is the first implementation lesson. It shows the complete `send()` path in one file:
define a request and its response type, implement a handler, register it, and send the
request.

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

## Send a typed request

A request's base class connects the request type to the response type returned by
`Mediator.send()`. The handler's return annotation separately describes what that handler
returns, and PyMediate checks the handler signature when the class is defined:

```python
@dataclass
class AddTask(Request[Task]):     # "sending AddTask responds with a Task"
    title: str

class AddTaskHandler(RequestHandler[AddTask]):
    async def __call__(self, request: AddTask) -> Task:
        ...                       # store the task, return it

task = await mediator.send(AddTask(title="Buy groceries"))
# `task` is inferred as Task — no cast, no isinstance narrowing needed.
assert task.task_id == 1          # typed attribute access
```

`AddTask(Request[Task])` makes `mediator.send(AddTask(...))` return `Task` to a static type
checker. The handler still declares `-> Task` so its own implementation can be checked.
`reveal_type(task)` reports `Task`, and `task.task_id` is a known `int` without a cast.

## Read the code

| File | What to read |
| --- | --- |
| [`app.py`](app.py) | **Start here.** One request, one handler, the wiring, and a demo. |
| [`test_app.py`](test_app.py) | The same round trip as tests: `uv run pytest` → `3 passed`. |

## Details

- A handler's `__call__` signature is validated when the class is defined, so a
  wrongly-annotated handler — including a plain `def` where `async def` is required —
  fails at import time, not at dispatch time.
- The handler receives its `TaskStore` dependency through its constructor.

## Where next

- [020-events](../020-events/) — publish one event to several independent handlers.
- [010-basic-sync](../010-basic-sync/) — the same request and response flow on
  `pymediate.sync`.
- The docs: [quick start](https://pymediate.sina-al.uk/docs/getting-started/quick-start) ·
  [requests & responses](https://pymediate.sina-al.uk/docs/guide/requests-responses).
