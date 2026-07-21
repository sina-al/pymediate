# 020-events

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/sina-al/pymediate?devcontainer_path=.devcontainer%2F020-events%2Fdevcontainer.json)

`publish()` sends one notification to every handler registered for that notification type. This example
publishes `TaskCompleted` to three independent asynchronous handlers and shows that they run
concurrently.

## Run

From this example directory:

```bash
uv sync
uv run python app.py
```

```text
Completing task 1: 'Buy groceries'
  notify  started
  stats   started
  audit   started
  audit   done    (task 1 logged)
  stats   done    (completions now 1)
  notify  done    (queued task completion for Buy groceries)
All notification handlers started before any finished; async publish was concurrent.

Archiving task 1 (no handlers registered for TaskArchived):
  publish returned; no matching handlers ran.
```

All three `started` lines appear before the first `done` line. The asynchronous mediator
starts each handler and then waits for all of them to finish. The synchronous version runs
the handlers one at a time.

## Publish one notification to several handlers

A notification reports that something happened and does not have a response value. Any number of
notification handlers can register for its exact type:

```python
@dataclass
class TaskCompleted(Notification):          # an announcement, not a request
    task_id: int
    title: str

class AuditLog(NotificationHandler[TaskCompleted]):
    async def __call__(self, notification: TaskCompleted) -> None:
        self._dashboard.feed.append(f"audit done (task {notification.task_id} logged)")
```

Register the handlers, then publish once:

```python
await mediator.publish(TaskCompleted(task_id=1, title="Buy groceries"))
# every notification handler runs concurrently; publish waits for all of them
```

`send` returns a typed response from one request handler. `publish` returns `None` after all
matching notification handlers finish.

## Compare asynchronous and synchronous delivery

The output shows the delivery difference between this example and its synchronous twin:

| | this example (asynchronous `publish`) | [020-events-sync](../020-events-sync/) (synchronous `publish`) |
| --- | --- | --- |
| Notification handlers run | **concurrently** — all start, then all finish | **sequentially**, in registration order |
| Feed shows | every `started` before any `done` | each `started`/`done` paired, one at a time |

Both examples use the same three handlers and the same notification.

## Read the code

| File | What to read |
| --- | --- |
| [`app.py`](app.py) | **Start here.** The `TaskCompleted` notification, three handlers, and a demo. |
| [`test_app.py`](test_app.py) | Plain `async def` tests via pytest-asyncio's auto mode: `uv run pytest` → `6 passed`. |

## Details

- **Publishing with no matching handlers succeeds.** `TaskArchived` has no handlers, so
  publishing it returns without changing the dashboard.
- **Notification delivery uses the exact type.** A handler registered for `TaskCompleted` receives only
  `TaskCompleted` — never a subclass, never a base class.
- **Concurrent handlers must be independent.** Because asynchronous delivery runs them at the
  same time, they must not depend on each other's effects (here each writes only its own
  feed lines and counter). If one handler raises, the rest still run and the failures
  surface together as an
  [`ExceptionGroup`](https://docs.python.org/3/library/exceptions.html#ExceptionGroup) you
  can split with `except*`.
- This demo publishes from `main` for clarity; in a larger app the request handler that
  completes the task would publish the notification itself, once the work is done.

## Where next

- [030-streaming](../030-streaming/) — return a sequence of typed chunks from one request.
- [020-events-sync](../020-events-sync/) — the same notification delivery on `pymediate.sync`.
- The docs: [notifications guide](https://pymediate.sina-al.uk/docs/guide/notifications) ·
  [core concepts](https://pymediate.sina-al.uk/docs/getting-started/concepts).
