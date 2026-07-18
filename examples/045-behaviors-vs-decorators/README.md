# 045-behaviors-vs-decorators

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/sina-al/pymediate?devcontainer_path=.devcontainer%2F045-behaviors-vs-decorators%2Fdevcontainer.json)

This example applies the same rate limit with a method decorator and with a
`PipelineBehavior`. Both receive a replaceable limiter; the difference is where the rule is
attached and which calls it covers.

## Run

From this directory:

```bash
uv sync
uv run taskboard
```

```text
== decorator: limiter injected into each handler ==
blocked on a direct call: 'AddTask' exceeded 2 calls
a second handler accepted 5 tasks with its own limiter

== behavior: limiter configured when the mediator is built ==
blocked during mediator dispatch: 'AddTask' exceeded 2 calls
a second mediator accepted 5 tasks with its configured behavior
```

## Method decorator

The decorator reads the limiter from the handler instance. A caller can give each handler a
different limiter through its constructor.

```python
def rate_limited(func):
    @functools.wraps(func)
    async def wrapper(self, request):
        self.limiter.check(type(request).__name__)
        return await func(self, request)
    return wrapper

class AddTaskHandler(RequestHandler[AddTask]):
    def __init__(self, store: TaskStore, limiter: RateLimiter) -> None:
        self._store = store
        self._limiter = limiter

    @rate_limited
    async def __call__(self, request: AddTask) -> Task: ...
```

The decorator belongs to this method. It runs whether the handler is reached through a
mediator or called directly.

## Pipeline behavior

The behavior is registered when the mediator is built. Its type parameter selects
`AddTask`, so the handler contains no rate-limiting code.

```python
class RateLimitBehavior(PipelineBehavior[AddTask]):
    def __init__(self, limiter: RateLimiter) -> None:
        self._limiter = limiter

    async def __call__(self, request: AddTask, next: Next[Task]) -> Task:
        self._limiter.check(type(request).__name__)
        return await next()

services.add(RateLimitBehavior(limiter))
services.add(AddTaskHandler(store))
```

The behavior runs only during `mediator.send(...)`. Calling `AddTaskHandler` directly bypasses
the mediator and therefore bypasses the behavior.

## Read the code

| File | What to read |
| --- | --- |
| [`src/taskboard/decorator.py`](src/taskboard/decorator.py) | Start here for the per-handler decorator. |
| [`src/taskboard/behavior.py`](src/taskboard/behavior.py) | The centrally configured behavior and mediator setup. |
| [`src/taskboard/limiter.py`](src/taskboard/limiter.py) | The shared limiter interface, `CallCountLimiter`, and `AlwaysAllow`. |
| [`src/taskboard/app.py`](src/taskboard/app.py) | The console output shown above. |
| [`tests/test_decorator.py`](tests/test_decorator.py) | Direct-call and per-handler behavior. |
| [`tests/test_behavior.py`](tests/test_behavior.py) | Mediator-only and per-mediator behavior. |

## Details

| Question | Decorator | Behavior |
| --- | --- | --- |
| Where is the rule configured? | On each decorated method. | In the mediator's service configuration. |
| Can its limiter be replaced? | Yes, through the handler constructor. | Yes, when building the mediator. |
| Does it cover direct calls? | Yes. | No; it covers mediator dispatch only. |
| How is it selected? | By decorating a callable. | By the behavior's request type. |

`CallCountLimiter` counts calls but does not implement a time window. A production rate limiter
also needs expiry, shared storage where required, and a policy for concurrent callers.

Run `uv run pytest` to execute the seven tests that define these differences.

## Where next

- [050-handler-composition](../050-handler-composition/) composes several operations through
  the mediator.
- [045-behaviors-vs-decorators-sync](../045-behaviors-vs-decorators-sync/) shows the same
  comparison with `pymediate.sync`.
- Read the [pipeline behaviors guide](https://pymediate.sina-al.uk/docs/guide/pipeline-behaviors).
