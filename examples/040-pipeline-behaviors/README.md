# 040-pipeline-behaviors

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/sina-al/pymediate?devcontainer_path=.devcontainer%2F040-pipeline-behaviors%2Fdevcontainer.json)

`PipelineBehavior` runs shared code before and after request handlers. This example applies
logging to every request, authorization and a transaction-boundary trace to commands, and
caching to selected queries.

## Run

From this example directory:

```bash
uv sync
uv run taskboard
```

```text
Created 'Buy groceries' (id=1)
GetTask handler ran 1 time(s) across 2 sends (cache served the rest)
Pipeline trace:
  log:enter AddTask
  authorization AddTask
  transaction:enter
  transaction:exit
  log:exit AddTask
  log:enter GetTask
  cache:miss GetTask
  log:exit GetTask
  log:enter GetTask
  cache:hit GetTask
  log:exit GetTask
```

Read the trace from top to bottom. The `AddTask` command passes through logging,
authorization, the transaction-boundary trace, and its handler. The `GetTask` query passes
through logging, caching, and its handler. On the second `GetTask`, caching returns a stored
response without calling the handler.

## Select requests by type

A behavior's type parameter selects the requests it receives:

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
command, so `AuthorizationBehavior` and `TransactionBehavior` (both `[Command]`) receive it.
`GetTask(Query, Request[Task])` is a query, so `CachingBehavior` (`[Query]`) receives it.
The mediator selects matching behaviors for each request with `isinstance()`.

## Control order and stop execution

**Registration order is execution order** — first registered is outermost:

```python
services.add(LoggingBehavior(trace))          # 1. outermost — sees every request
services.add(AuthorizationBehavior(principal, trace))  # 2. commands only
services.add(CachingBehavior(cache, trace))   # 3. queries only; may short-circuit
services.add(TransactionBehavior(trace))      # 4. innermost — commands only
```

`next()` is the rest of the pipeline. A behavior that returns **without** calling it
stops everything nested inside it. A cache hit returns the cached response this way, and an
authorization failure raises before calling the handler. Logging is registered first, so
its `log:exit` entry is still recorded when caching returns early.

For conditions the type parameter can't express, override `should_apply()`. `CachingBehavior`
uses it so a query can opt out of caching at runtime — `ListOpenTasks` does, because the
open-task list changes too often to cache:

```python
@classmethod
def should_apply(cls, request):
    return isinstance(request, Query) and request.cacheable
```

## Read the code

| File | What to read |
| --- | --- |
| [`src/taskboard/behaviors.py`](src/taskboard/behaviors.py) | **Start here.** The four behaviors, each selected by its type parameter. |
| [`src/taskboard/domain.py`](src/taskboard/domain.py) | The `Command` and `Query` families, requests, handlers, and in-memory dependencies. |
| [`src/taskboard/app.py`](src/taskboard/app.py) | `build_mediator` (registration order = execution order) and the demo. |
| [`tests/test_pipeline.py`](tests/test_pipeline.py) | Checks ordering, cached responses, `should_apply`, authorization, and transaction-boundary error tracing: `uv run pytest` → `7 passed`. |

## Details

- Behaviors wrap `send()` only. `publish()` delivers events directly to event handlers, so
  event-specific logging or timing belongs in those handlers.
- `TransactionBehavior` records where a real transaction manager would enter, exit, or see
  an error. It does not change or restore `TaskStore` state.
- `FakeCache` demonstrates returning a stored response. A production cache also needs
  stable keys, serialization, expiry, and invalidation.
- Read [010-basic](../010-basic/) first if `send()` is unfamiliar.

## Where next

- [045-behaviors-vs-decorators](../045-behaviors-vs-decorators/) — compare a behavior with
  a decorator that performs the same rate-limit check.
- [040-pipeline-behaviors-sync](../040-pipeline-behaviors-sync/) — the same pipeline on
  `pymediate.sync`.
- The docs: [pipeline behaviors guide](https://pymediate.sina-al.uk/docs/guide/pipeline-behaviors).
