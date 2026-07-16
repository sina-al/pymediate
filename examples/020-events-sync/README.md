# 020-events-sync

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/sina-al/pymediate?devcontainer_path=.devcontainer%2F020-events-sync%2Fdevcontainer.json)

**How do I make one thing happening trigger reactions in three different places — without
an event loop?** You publish an event. [020-events](../020-events/)'s fan-out on
`pymediate.sync`, PyMediate's synchronous mirror: finishing a task announces
`TaskCompleted`, and three unrelated subscribers pick it up — a notifier, a stats counter,
and an audit log. Read 020-events first if you haven't; this example is best enjoyed as a
diff against it.

## Run it

```bash
cd examples/020-events-sync
uv sync
uv run python app.py
```

```text
Completing task 1: 'Buy groceries'
  notify  started
  notify  done    (queued: Nice work! Buy groceries is done.)
  stats   started
  stats   done    (completions now 1)
  audit   started
  audit   done    (task 1 logged)
Each subscriber finished before the next started — sync publish is sequential.

Archiving task 1 (nothing subscribes to TaskArchived):
  publish returned, no handlers ran — zero subscribers is a valid no-op.
```

Read the feed: each subscriber's `started` is immediately followed by its own `done`,
in registration order. That is the one real difference from the async twin, where all
three `started` lines print before the first `done`. Same three subscribers, same `publish`
call — only the mediator changes.

## What changed from 020-events

Everything imports from `pymediate.sync` instead of `pymediate`; subscribers declare a
plain `def __call__`, and publishing blocks — no `await`, no `asyncio.run()`. `Event`
and `Services` are the *same objects* in both namespaces — only `EventHandler` and
`Mediator` have sync variants.

```python
from pymediate.sync import Event, EventHandler, Mediator, Services

class AuditLog(EventHandler[TaskCompleted]):
    def __call__(self, event: TaskCompleted) -> None:
        self._dashboard.feed.append(f"audit done (task {event.task_id} logged)")

mediator.publish(TaskCompleted(task_id=1, title="Buy groceries"))  # runs subscribers in turn
```

The sync mediator runs the subscribers **sequentially, in registration order** — one
finishes before the next begins. The async twin runs them concurrently. Fan-out, exact-type
dispatch, and the zero-subscriber no-op are otherwise identical.

## The files

| File | What it is |
| --- | --- |
| [`app.py`](app.py) | **Start here.** The `TaskCompleted` event, three subscribers, and a small demo. |
| [`test_app.py`](test_app.py) | The same flows as tests: `uv run pytest` → `6 passed`. |

## Small print

- **Publishing to nobody is a no-op, not an error.** `TaskArchived` has no subscribers, so
  publishing it does nothing and raises nothing — zero subscribers is a legitimate state.
  Erroring would couple every publisher to whether a subscriber happens to exist.
- **Fan-out is by exact type.** A handler subscribed to `TaskCompleted` receives only
  `TaskCompleted` — never a subclass, never a base class.
- **Every subscriber runs, even if one raises.** Delivery doesn't stop at the first failure;
  once every subscriber has run, the failures surface together as an
  [`ExceptionGroup`](https://docs.python.org/3/library/exceptions.html#ExceptionGroup) you
  can split with `except*`.
- This demo publishes from `main` for clarity; in a larger app the request handler that
  completes the task would publish the event itself, once the work is done.

## Where next

- [020-events](../020-events/) — the async original, where the three subscribers run
  concurrently. Diff it against this one.
- [090-adapters-sync](../090-adapters-sync/) — the same core pattern serving Flask,
  FastAPI, and a CLI at once.
- The docs: [events guide](https://pymediate.sina-al.uk/docs/guide/events) ·
  [core concepts](https://pymediate.sina-al.uk/docs/getting-started/concepts).
