# basic-async

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/sina-al/pymediate?devcontainer_path=.devcontainer%2Fbasic-async%2Fdevcontainer.json)

The smallest useful PyMediate application: an in-memory task board in one file. If you're
new to PyMediate, **start with this example** — everything else in `examples/` builds on
the pattern shown here.

## Run it

```bash
cd examples/basic-async
uv sync
uv run python app.py
```

```text
Created: Task(task_id=1, title='Buy groceries', done=False)
Open: Write the release notes
Audited: AddTask: task 1
Audited: AddTask: task 2
Audited: CompleteTask: task 1
```

## The idea, in ten lines

A request declares what it responds with, right in its type:

```python
@dataclass
class AddTask(BoardMutation):        # a Request[Task]: "sending AddTask gives back a Task"
    title: str

class AddTaskHandler(RequestHandler[AddTask]):
    async def __call__(self, request: AddTask) -> Task:
        ...  # create the task, return it
```

Register one handler per request, then send:

```python
task = await mediator.send(AddTask(title="Buy groceries"))   # typed: task is a Task
```

Your IDE and type checker know `task` is a `Task` — and awaiting
`mediator.send(ListOpenTasks())` gives a `list[Task]` — with no casts and no
stringly-typed routing. That's the whole trick.

## One more trick: the audit behavior

A **pipeline behavior** wraps dispatch like middleware, and its type parameter decides
which requests it applies to:

```python
class AuditTrail(PipelineBehavior[BoardMutation]):   # wraps AddTask & CompleteTask only
    async def __call__(self, request, next):
        task = await next()                          # run the handler
        self._log.append(f"{type(request).__name__}: task {task.task_id}")
        return task
```

`ListOpenTasks` doesn't subclass `BoardMutation`, so reads skip the audit — no
registration lists to maintain, the types carry the routing.

## The files

| File | What it is |
| --- | --- |
| [`app.py`](app.py) | **Start here.** Requests, async handlers, the `AuditTrail` behavior, and a small demo. |
| [`test_app.py`](test_app.py) | Plain `async def` tests via pytest-asyncio's auto mode: `uv run pytest` → `7 passed`. |

## Small print

- A handler's `__call__` signature is validated when the class is defined, so a
  wrongly-annotated handler — including a plain `def` where `async def` is required —
  fails at import time, not at dispatch time.
- Handlers take their dependencies (here, a shared `TaskStore`) through plain
  constructors — no framework, no magic.

## Where next

- [basic-sync](../basic-sync/) — this exact board without the event loop, on
  `pymediate.sync`.
- [adapters-async](../adapters-async/) — this core pattern serving FastAPI, aiohttp, and
  an async CLI at once.
- The docs: [quick start](https://pymediate.sina-al.uk/docs/getting-started/quick-start) ·
  [pipeline behaviors](https://pymediate.sina-al.uk/docs/guide/pipeline-behaviors).
