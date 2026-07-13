# 045-behaviors-vs-decorators-sync

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/sina-al/pymediate?devcontainer_path=.devcontainer%2F045-behaviors-vs-decorators-sync%2Fdevcontainer.json)

The synchronous mirror of [045-behaviors-vs-decorators](../045-behaviors-vs-decorators/),
on `pymediate.sync` — no event loop. Why bother with a whole `PipelineBehavior` class when
a plain `@decorator` on `__call__` does the same job with less ceremony? It does — right up
until the concern needs a dependency you want to swap. This example rate-limits the
identical operation two ways: once with a decorator, once with a behavior, and shows
exactly where the decorator runs out of road.

## Run it

```bash
cd examples/045-behaviors-vs-decorators-sync
uv sync
uv run taskboard
```

```text
== decorator version: quota bound at import time ==
blocked: 'AddTask' exceeded 2 calls
(no constructor argument raises this quota — only patching decorator._limiter)

== behavior version: same quota, passed in ==
blocked: 'AddTask' exceeded 2 calls

== behavior version, swapped for a bulk import — nothing else changes ==
added 5 tasks: a different limiter argument, same handler, same behavior class
```

Both versions enforce the same quota of 2. The difference is what it takes to *change*
that quota for one caller without touching the other — the last section shows a mediator
built with a permissive limiter, nothing else different.

## The money shot: nowhere to put the dependency vs. an ordinary constructor argument

```python
# decorator.py — bound once, at import time. Every call shares this exact instance.
_limiter: RateLimiter = FixedWindowLimiter(limit=2)

def rate_limited(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        _limiter.check("AddTask")          # always THIS limiter — no way in
        return func(*args, **kwargs)
    return wrapper

class AddTaskHandler(RequestHandler[AddTask]):
    @rate_limited
    def __call__(self, request: AddTask) -> Task: ...
```

```python
# behavior.py — an ordinary constructor argument.
class RateLimitBehavior(PipelineBehavior[Request]):
    def __init__(self, limiter: RateLimiter) -> None:
        self._limiter = limiter                # whichever one you passed in

    def __call__(self, request, next):
        self._limiter.check(type(request).__name__)
        return next()

mediator = build_mediator(limiter=AlwaysAllow())   # swap it — that's the whole change
```

A decorator wraps a function at class-body evaluation time — before any instance exists —
so it has no parameter through which to *receive* a collaborator. The only place left to
get one from is a name already in scope at import time, which in practice means a
module-level singleton. A `PipelineBehavior` is just an object: its dependency arrives
through `__init__`, exactly like a handler's does.

## Where the decorator's friction actually bites

| Decorator version | Behavior version |
| --- | --- |
| `_limiter` is one module-level instance; every `AddTaskHandler` shares it, forever. | `limiter` is a constructor argument; every `RateLimitBehavior` gets the one it was given. |
| Swapping it in a test means monkeypatching `taskboard.decorator._limiter`, then restoring it — see the `_fresh_module_limiter` fixture in the tests. | Swapping it in a test means constructing `build_mediator(limiter=...)` — see `test_swapping_the_limiter_is_a_constructor_argument`. |
| Two handler instances can't have different quotas — there's only one `_limiter`. | Two mediators can have completely independent quotas — see `test_two_mediators_keep_independent_limiters`. |

`uv run pytest` → `6 passed`: `tests/test_decorator_friction.py` proves the friction (a
`_fresh_module_limiter` fixture is *required* just to stop tests bleeding into each other);
`tests/test_behavior_swap.py` proves the swap is trivial, no fixture required.

## The files

| File | What it is |
| --- | --- |
| [`src/taskboard/decorator.py`](src/taskboard/decorator.py) | **Start here.** The decorator version — a module-level `_limiter`, bound at import time. |
| [`src/taskboard/behavior.py`](src/taskboard/behavior.py) | The behavior version — the same limiter, now a constructor argument. |
| [`src/taskboard/limiter.py`](src/taskboard/limiter.py) | `RateLimiter`, `FixedWindowLimiter` (the real thing), `AlwaysAllow` (the test double). |
| [`src/taskboard/domain.py`](src/taskboard/domain.py) | `Task`/`TaskStore` — the plain domain both versions wrap. |
| [`tests/test_decorator_friction.py`](tests/test_decorator_friction.py) | The friction: shared state, a required reset fixture, no per-instance quotas. |
| [`tests/test_behavior_swap.py`](tests/test_behavior_swap.py) | The fix: swap the limiter as a constructor argument, no fixture needed. |

## Small print

- This assumes you've already met `PipelineBehavior` — if not, start with
  [040-pipeline-behaviors-sync](../040-pipeline-behaviors-sync/), then come back.
- The decorator isn't wrong for *every* cross-cutting concern — one with no dependency at
  all (a pure `@functools.cache`, a bare `try`/`except` wrapper) has nothing to inject, so
  there's nothing for a behavior to buy you. The revelation here is specifically about the
  moment a concern *needs* a swappable collaborator.
- `FixedWindowLimiter` never resets in this demo (no window expiry) — realistic enough to
  make the point, not a production rate limiter.

## Where next

- [045-behaviors-vs-decorators](../045-behaviors-vs-decorators/) — the async default this
  mirrors, on the top-level `pymediate` API.
- [with-dependency-injector](../with-dependency-injector/) — when even constructing the
  behavior by hand gets old, a DI container does it for you.
- The docs: [pipeline behaviors guide](https://pymediate.sina-al.uk/docs/guide/pipeline-behaviors),
  [dependency injection guide](https://pymediate.sina-al.uk/docs/guide/dependency-injection).
