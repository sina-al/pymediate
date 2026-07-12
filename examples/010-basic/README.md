# 010-basic

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/sina-al/pymediate?devcontainer_path=.devcontainer%2F010-basic%2Fdevcontainer.json)

You came to send a typed request and get a typed response back. Here's the whole loop in
one file — no behaviors, no events, no DI. If you're new to PyMediate, **start here**;
every other example builds on this.

## Run it

```bash
cd examples/010-basic
uv sync
uv run python app.py
```

```text
Created: Task(task_id=1, title='Buy groceries', done=False)
Assigned id: 1
```

## The whole loop

A request declares the type it responds with, right in its base class. One handler
resolves it. You send, and the response comes back typed:

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

That last comment is the point. The response type you wrote **once** — on
`AddTask(Request[Task])` — is what your IDE and type checker report at the call site.
`reveal_type(task)` says `Task`; `task.task_id` is a known `int`. No casts, no
stringly-typed routing, no lookup table to keep in sync. The mediator carries the type
from the request through to the response for you.

## The files

| File | What it is |
| --- | --- |
| [`app.py`](app.py) | **Start here.** One request, one handler, the wiring, and a tiny demo. |
| [`test_app.py`](test_app.py) | The same round trip as tests: `uv run pytest` → `3 passed`. |

## Small print

- A handler's `__call__` signature is validated when the class is defined, so a
  wrongly-annotated handler — including a plain `def` where `async def` is required —
  fails at import time, not at dispatch time.
- The handler takes its dependency (here, a shared `TaskStore`) through a plain
  constructor — no framework, no magic.

## Where next

- [010-basic-sync](../010-basic-sync/) — this exact loop without the event loop, on
  `pymediate.sync`.
- The docs: [quick start](https://pymediate.sina-al.uk/docs/getting-started/quick-start) ·
  [requests & responses](https://pymediate.sina-al.uk/docs/guide/requests-responses).
