# 020-events

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/sina-al/pymediate?devcontainer_path=.devcontainer%2F020-events%2Fdevcontainer.json)

**How do I make one thing happening trigger reactions in three different places?** You
publish an event. `send` routes one request to one handler and hands you its answer;
`publish` announces a fact and lets *any number* of subscribers react — none, one, or many —
and the publisher never learns who listened. Here, finishing a task announces
`TaskCompleted`, and three unrelated subscribers pick it up: a notifier, a stats counter,
and an audit log.

## Run it

```bash
cd examples/020-events
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
  notify  done    (queued: Nice work! Buy groceries is done.)
Every subscriber started before any finished — async publish ran them concurrently.

Archiving task 1 (nothing subscribes to TaskArchived):
  publish returned, no handlers ran — zero subscribers is a valid no-op.
```

Read the feed: all three `started` lines print *before* the first `done`. That ordering is
only possible because the async mediator ran the subscribers together — it started each one,
then awaited them all. (The `-sync` twin prints the same subscribers strictly paired, one
finishing before the next begins — [see below](#sync-vs-async).)

## The idea, in ten lines

An event is a plain announcement — no response, no single owner. Any number of handlers
subscribe to it by type:

```python
@dataclass
class TaskCompleted(Event):          # an announcement, not a request
    task_id: int
    title: str

class AuditLog(EventHandler[TaskCompleted]):
    async def __call__(self, event: TaskCompleted) -> None:
        self._dashboard.feed.append(f"audit done (task {event.task_id} logged)")
```

Register as many subscribers as you like, then publish once:

```python
await mediator.publish(TaskCompleted(task_id=1, title="Buy groceries"))
# every subscriber runs — concurrently — and publish awaits them all
```

`send` gives back a typed response from exactly one handler; `publish` returns `None` and
notifies them all. That's the difference between *asking* and *announcing*.

## Sync vs. async

The delivery model is the one real difference between this example and its `-sync` twin, and
the output makes it visible:

| | this example (async `publish`) | [020-events-sync](../020-events-sync/) (sync `publish`) |
| --- | --- | --- |
| Subscribers run | **concurrently** — all start, then all finish | **sequentially**, in registration order |
| Feed shows | every `started` before any `done` | each `started`/`done` paired, one at a time |

Same three subscribers, same `publish` call — only the mediator changes. Diffing the pair is
the fastest way to see it.

## The files

| File | What it is |
| --- | --- |
| [`app.py`](app.py) | **Start here.** The `TaskCompleted` event, three subscribers, and a small demo. |
| [`test_app.py`](test_app.py) | Plain `async def` tests via pytest-asyncio's auto mode: `uv run pytest` → `6 passed`. |

## Small print

- **Publishing to nobody is a no-op, not an error.** `TaskArchived` has no subscribers, so
  publishing it does nothing and raises nothing — zero subscribers is a legitimate state.
  Erroring would couple every publisher to whether a subscriber happens to exist.
- **Fan-out is by exact type.** A handler subscribed to `TaskCompleted` receives only
  `TaskCompleted` — never a subclass, never a base class.
- **Concurrent subscribers must be independent.** Because async delivery runs them at the
  same time, they must not depend on each other's effects (here each writes only its own
  feed lines and counter). If one subscriber raises, the rest still run and the failures
  surface together as an
  [`ExceptionGroup`](https://docs.python.org/3/library/exceptions.html#ExceptionGroup) you
  can split with `except*`.
- This demo publishes from `main` for clarity; in a larger app the request handler that
  completes the task would publish the event itself, once the work is done.

## Where next

- [020-events-sync](../020-events-sync/) — the same fan-out on `pymediate.sync`, where
  delivery is sequential. Diff it against this one.
- [basic](../basic/) — the `send` side of the mediator: typed requests, one handler each.
- The docs: [events guide](https://pymediate.sina-al.uk/docs/guide/events) ·
  [core concepts](https://pymediate.sina-al.uk/docs/getting-started/concepts).
