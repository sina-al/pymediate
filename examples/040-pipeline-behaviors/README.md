# 040-pipeline-behaviors

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/sina-al/pymediate?devcontainer_path=.devcontainer%2F040-pipeline-behaviors%2Fdevcontainer.json)

How do you add logging, authorization, caching, and transactions to a handful of
handlers *without copy-pasting the same four blocks into every one of them*? In PyMediate
each concern gets **one home** — a `PipelineBehavior` that wraps dispatch like middleware
— and **its type parameter decides which requests it wraps**. No registration lists, no
`if isinstance` ladders. This example composes four behaviors into an ordered stack over a
task board.

## Run it

```bash
cd examples/040-pipeline-behaviors
uv sync
uv run taskboard
```

```text
Created 'Buy groceries' (id=1)
GetTask handler ran 1 time(s) across 2 sends (cache served the rest)
Pipeline trace:
  log:enter AddTask
  authz AddTask
  tx:begin
  tx:commit
  log:exit AddTask
  log:enter GetTask
  cache:miss GetTask
  log:exit GetTask
  log:enter GetTask
  cache:hit GetTask
  log:exit GetTask
```

Read the trace top to bottom: the `AddTask` **command** flows through logging →
authorization → transaction → handler, while the `GetTask` **query** flows through logging
→ caching → handler. Same registration, different stack — because each behavior routes on
its type parameter. The second `GetTask` is a `cache:hit`, so the handler never runs: that
line proves the short-circuit.

## The money shot: the type parameter is the router

A behavior names the requests it applies to in its type parameter. That's the whole
routing mechanism:

```python
class LoggingBehavior(PipelineBehavior[Request]):        # universal — every request
    async def __call__(self, request, next):
        self._trace.append(f"log:enter {type(request).__name__}")
        try:
            return await next()                          # run the rest of the pipeline
        finally:
            self._trace.append(f"log:exit {type(request).__name__}")

class AuthorizationBehavior(PipelineBehavior[Command]):   # selective — commands only
    async def __call__(self, request, next):
        if not self._principal.can_write:
            raise AccessDeniedError(...)                  # never calls next(): request denied
        return await next()
```

`Command` and `Query` are marker base classes. `AddTask(Command, Request[Task])` is a
command, so `AuthorizationBehavior` and `TransactionBehavior` (both `[Command]`) wrap it;
`GetTask(Query, Request[Task])` is a query, so only `CachingBehavior` (`[Query]`) does. The
mediator filters behaviors per request with `isinstance()` — you never maintain a list of
"which behavior applies where."

## Ordering and short-circuiting

**Registration order is execution order** — first registered is outermost:

```python
services.add(LoggingBehavior(trace))          # 1. outermost — sees every request
services.add(AuthorizationBehavior(principal, trace))  # 2. commands only
services.add(CachingBehavior(cache, trace))   # 3. queries only; may short-circuit
services.add(TransactionBehavior(store, trace))  # 4. innermost — commands only
```

`next()` is the rest of the pipeline. A behavior that returns **without** calling it
short-circuits everything nested inside — that's exactly what a cache hit wants (skip the
handler) and what an authorization failure wants (never reach the handler). Skipping
`next()` anywhere else would be a silent bug. Notice logging is registered outermost, so
its `log:exit` still runs when caching short-circuits inside it.

For conditions the type parameter can't express, override `should_apply()`. `CachingBehavior`
uses it so a query can opt out of caching at runtime — `ListOpenTasks` does, because the
open-task list changes too often to cache:

```python
@classmethod
def should_apply(cls, request):
    return isinstance(request, Query) and request.cacheable
```

## The files

| File | What it is |
| --- | --- |
| [`src/taskboard/behaviors.py`](src/taskboard/behaviors.py) | **Start here.** The four behaviors, each routed by its type parameter. |
| [`src/taskboard/domain.py`](src/taskboard/domain.py) | The task board: `Command`/`Query` families, requests, handlers, and fake store/cache/principal. |
| [`src/taskboard/app.py`](src/taskboard/app.py) | `build_mediator` (registration order = execution order) and the demo. |
| [`tests/test_pipeline.py`](tests/test_pipeline.py) | Asserts the stack ordering, the cache short-circuit, `should_apply`, and rollback: `uv run pytest` → `7 passed`. |

## Small print

- Behaviors wrap `send()` only. `publish()` delivers events straight to their handlers —
  cross-cutting concerns for events live in the event handlers themselves.
- The store, cache, and principal are deliberately fake, in-process stand-ins. A real
  Redis client or database session drops in behind the same calls without touching a
  behavior.
- This example assumes you've met `send()` already — if not, start with
  [basic](../basic/), then come back.

## Where next

- [040-pipeline-behaviors-sync](../040-pipeline-behaviors-sync/) — the same stack on
  `pymediate.sync`, no event loop.
- [events](../events/) — the mediator's other half: `publish()` fans one event out to many
  handlers.
- The docs: [pipeline behaviors guide](https://pymediate.sina-al.uk/docs/guide/pipeline-behaviors).
