# basic-aio

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/sina-al/pymediate?devcontainer_path=.devcontainer%2Fbasic-aio%2Fdevcontainer.json)

[basic-sync](../basic-sync/)'s task board again — now fully async, plus one new trick: a
**pipeline behavior** that audits every mutation. Read basic-sync first if you haven't;
this example is best enjoyed as a diff against it.

## Run it

```bash
cd examples/basic-aio
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

## What changed from basic-sync

Handlers come from `pymediate.aio` and declare `async def __call__`; sending is awaited.
Requests and `Services` are the same classes as the sync package — only `Handler`,
`Mediator`, and `PipelineBehavior` have async variants.

```python
class AddTaskHandler(Handler[AddTask]):              # from pymediate.aio
    async def __call__(self, request: AddTask) -> Task:
        await asyncio.sleep(0)                       # a real app would await its datastore
        ...

task = await mediator.send(AddTask(title="Buy groceries"))   # still fully typed
```

And the new trick — a behavior wraps dispatch like middleware, and its type parameter
decides which requests it applies to:

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
| [`app.py`](app.py) | **Start here.** The async task board + the `AuditTrail` behavior. |
| [`test_app.py`](test_app.py) | Plain `async def` tests via pytest-asyncio's auto mode: `uv run pytest` → `7 passed`. |

## Where next

- [adapters-aio](../adapters-aio/) — this core pattern serving FastAPI, aiohttp, and an
  async CLI at once.
- The docs: [pipeline behaviors](https://pymediate.sina-al.uk/docs/guide/pipeline-behaviors) ·
  [core concepts](https://pymediate.sina-al.uk/docs/getting-started/concepts).
