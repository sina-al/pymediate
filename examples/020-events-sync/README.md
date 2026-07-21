# 020-events-sync

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/sina-al/pymediate?devcontainer_path=.devcontainer%2F020-events-sync%2Fdevcontainer.json)

`pymediate.sync.Mediator.publish()` sends one notification to every handler registered for that
notification type. This example publishes `TaskCompleted` to three handlers and shows that they run
sequentially in registration order.

## Run

From this example directory:

```bash
uv sync
uv run python app.py
```

```text
Completing task 1: 'Buy groceries'
  notify  started
  notify  done    (queued task completion for Buy groceries)
  stats   started
  stats   done    (completions now 1)
  audit   started
  audit   done    (task 1 logged)
Each notification handler finished before the next started; synchronous publish was sequential.

Archiving task 1 (no handlers registered for TaskArchived):
  publish returned; no matching handlers ran.
```

Each handler's `started` line is immediately followed by its own `done` line. The
asynchronous version starts all three handlers before any finishes.

## Publish one notification synchronously

Everything imports from `pymediate.sync` instead of `pymediate`; notification handlers declare a
plain `def __call__`, and publishing blocks — no `await`, no `asyncio.run()`. `Notification`
and `Services` are the *same objects* in both namespaces — only `NotificationHandler` and
`Mediator` have sync variants.

```python
from pymediate.sync import Notification, NotificationHandler, Mediator, Services

class AuditLog(NotificationHandler[TaskCompleted]):
    def __call__(self, notification: TaskCompleted) -> None:
        self._dashboard.feed.append(f"audit done (task {notification.task_id} logged)")

mediator.publish(TaskCompleted(task_id=1, title="Buy groceries"))  # runs handlers in order
```

The synchronous mediator runs the handlers **sequentially, in registration order**. The
asynchronous version runs them concurrently. Exact-type delivery and publishing with no
matching handlers are otherwise identical.

## Read the code

| File | What to read |
| --- | --- |
| [`app.py`](app.py) | **Start here.** The `TaskCompleted` notification, three handlers, and a demo. |
| [`test_app.py`](test_app.py) | The same flows as tests: `uv run pytest` → `6 passed`. |

## Details

- **Publishing with no matching handlers succeeds.** `TaskArchived` has no handlers, so
  publishing it returns without changing the dashboard.
- **Notification delivery uses the exact type.** A handler registered for `TaskCompleted` receives only
  `TaskCompleted` — never a subclass, never a base class.
- **Every handler runs, even if one raises.** Delivery does not stop at the first failure;
  once every handler has run, the failures surface together as an
  [`ExceptionGroup`](https://docs.python.org/3/library/exceptions.html#ExceptionGroup) you
  can split with `except*`.
- This demo publishes from `main` for clarity; in a larger app the request handler that
  completes the task would publish the notification itself, once the work is done.

## Where next

- [030-streaming-sync](../030-streaming-sync/) — return a sequence of typed chunks from one
  synchronous request.
- [020-events](../020-events/) — the asynchronous version, where the three handlers run
  concurrently.
- The docs: [notifications guide](https://pymediate.sina-al.uk/docs/guide/notifications) ·
  [core concepts](https://pymediate.sina-al.uk/docs/getting-started/concepts).
