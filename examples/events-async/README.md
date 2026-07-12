# events-async

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/sina-al/pymediate?devcontainer_path=.devcontainer%2Fevents-async%2Fdevcontainer.json)

The other half of the mediator: **`publish`**. Where `send` routes one request to one
handler, `publish` fans one event out to *every* handler subscribed to it. Here, finishing
a task announces `TaskCompleted`, and three unrelated handlers react — an audit log, a
notifier, and a metrics counter — none aware of the others.

## Run it

```bash
cd examples/events-async
uv sync
uv run python app.py
```

```text
Completed: Buy groceries
Audit log: ['task 1 completed: Buy groceries']
Notifications: ["Nice work! 'Buy groceries' is done."]
Metrics: {'completed': 1}
```

## The idea, in ten lines

An event is a plain announcement — no response, no single owner. Any number of handlers
subscribe to it by type:

```python
@dataclass
class TaskCompleted(Event):        # an announcement, not a request
    task_id: int
    title: str

class AuditLog(EventHandler[TaskCompleted]):
    async def __call__(self, event: TaskCompleted) -> None:
        self._entries.append(f"task {event.task_id} completed: {event.title}")
```

Register as many handlers as you like, then publish once:

```python
await mediator.publish(TaskCompleted(task_id=1, title="Buy groceries"))
# every subscriber runs — concurrently — and publish awaits them all
```

`send` gives back a typed response from exactly one handler; `publish` returns `None` and
notifies them all. That's the difference between *asking* and *announcing*.

## The files

| File | What it is |
| --- | --- |
| [`app.py`](app.py) | **Start here.** Requests, the `TaskCompleted` event, three subscribers, and a small demo. |
| [`test_app.py`](test_app.py) | Plain `async def` tests via pytest-asyncio's auto mode: `uv run pytest` → `6 passed`. |

## Small print

- **Fan-out is by exact type.** A handler subscribed to `TaskCompleted` receives only
  `TaskCompleted` — never a subclass, never a base. Publishing an event nobody subscribed
  to is a silent no-op, not an error.
- **The subscribers run concurrently** (`await mediator.publish(...)` awaits them together),
  so each owns its own sink here rather than sharing mutable state. If one handler raises,
  the rest still run and the failures surface together as an
  [`ExceptionGroup`](https://docs.python.org/3/library/exceptions.html#ExceptionGroup) you
  can split with `except*`.
- This demo publishes from `main` for clarity; in a larger app the `CompleteTask` handler
  would emit the event itself once the work is done.

## Where next

- [basic-async](../basic-async/) — the `send` side of the mediator: typed requests, one
  handler each, and a pipeline behavior.
- A sync mirror on `pymediate.sync` (`events-sync`) is a planned follow-up.
- The docs: [events guide](https://pymediate.sina-al.uk/docs/guide/events) ·
  [core concepts](https://pymediate.sina-al.uk/docs/getting-started/concepts).
