# basic-sync

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/sina-al/pymediate?devcontainer_path=.devcontainer%2Fbasic-sync%2Fdevcontainer.json)

The smallest useful PyMediate application: an in-memory task board in one file. If you're
new to PyMediate, **start with this example** — everything else in `examples/` builds on
the pattern shown here.

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

## The idea, in ten lines

A request declares what it responds with, right in its type:

```python
@dataclass
class AddTask(Request[Task]):        # "sending AddTask gives back a Task"
    title: str

class AddTaskHandler(Handler[AddTask]):
    def __call__(self, request: AddTask) -> Task:
        ...  # create the task, return it
```

Register one handler per request, then send:

```python
task = mediator.send(AddTask(title="Buy groceries"))   # typed: task is a Task
```

Your IDE and type checker know `task` is a `Task` — and `mediator.send(ListOpenTasks())`
is a `list[Task]` — with no casts and no stringly-typed routing. That's the whole trick.

## The files

| File | What it is |
| --- | --- |
| [`app.py`](app.py) | **Start here.** Requests, handlers, wiring, and a small demo — about 100 lines. |
| [`test_app.py`](test_app.py) | The same flows as tests: `uv run pytest` → `6 passed`. |

## Small print

- A handler's `__call__` signature is validated when the class is defined, so a
  wrongly-annotated handler fails at import time, not at dispatch time.
- Handlers take their dependencies (here, a shared `TaskStore`) through plain
  constructors — no framework, no magic.

## Where next

- [basic-aio](../basic-aio/) — this exact example with `async def` handlers, plus a
  pipeline behavior.
- [adapters-sync](../adapters-sync/) — the same core pattern serving Flask, FastAPI, and
  a CLI at once.
- The docs: [quick start](https://pymediate.sina-al.uk/docs/getting-started/quick-start) ·
  [core concepts](https://pymediate.sina-al.uk/docs/getting-started/concepts).
