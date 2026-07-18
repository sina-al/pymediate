# 100-dependency-injection

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/sina-al/pymediate?devcontainer_path=.devcontainer%2F100-dependency-injection%2Fdevcontainer.json)

How do my handlers get their dependencies at scale — one repository shared everywhere,
a fresh helper every dispatch, or something in between? PyMediate's optional **`di`
extra** hands that off to a real [dependency-injector](https://python-dependency-injector.ets-labs.org/)
container, resolved **by type, not by provider name**, and this example shows all three
lifetimes side by side: **Factory** (rebuilt per dispatch), **Singleton** (app-wide), and
**`ContextLocalSingleton`** (one instance per logical scope — a request, in a real app).

## Run it

```bash
cd examples/100-dependency-injection
uv sync
uv run python app.py
```

```text
Registered: User(user_id=1, username='alice')
Unit of work: ['begin', "registered 'alice'", 'commit']
Registered: User(user_id=2, username='bob')
Unit of work: ['begin', "registered 'bob'", 'commit']
```

Two registrations, two separate scopes — bob's unit of work carries no trace of alice's.

## Three lifetimes, one container

```python
class AppContainer(containers.DeclarativeContainer):
    repository = providers.Singleton(UserRepository)           # one instance, app-wide
    unit_of_work = providers.ContextLocalSingleton(UnitOfWork)  # one instance per scope

    transaction_behavior = providers.Factory(TransactionLoggingBehavior, unit_of_work=unit_of_work)
    register_user_handler = providers.Factory(                  # fresh instance per dispatch
        RegisterUserHandler, repository=repository, unit_of_work=unit_of_work
    )

mediator = Mediator(DependencyInjectorServiceProvider(AppContainer()))
user = await mediator.send(RegisterUser(username="alice"))   # typed: user is a User
```

PyMediate never sees the wiring — only the finished container, resolved by the concrete
type of each handler and behavior. Provider names (`register_user_handler`, …) are for
humans; `DependencyInjectorServiceProvider` matches by type.

## The scoped lifetime: `ContextLocalSingleton`

`repository` is a `Singleton` — every request shares the exact same `UserRepository`.
`unit_of_work` is different: it's a `ContextLocalSingleton`, scoped to one logical unit
of work via `contextvars`. Both `RegisterUserHandler` and `TransactionLoggingBehavior`
ask the container for `unit_of_work` independently — within one dispatch, they get the
**same** instance, so their writes interleave:

```python
class TransactionLoggingBehavior(PipelineBehavior[Request]):
    async def __call__(self, request, next):
        self._unit_of_work.record("begin")
        response = await next()          # RegisterUserHandler records here, same instance
        self._unit_of_work.record("commit")
        return response
```

```text
['begin', "registered 'alice'", 'commit']
```

Calling `container.unit_of_work.reset()` — what a real ASGI/WSGI adapter does once per
incoming request — clears the cached instance, so the *next* dispatch gets a fresh
`UnitOfWork` with no memory of the last one. That's the scope boundary, made explicit.

## The files

| File | What it is |
| --- | --- |
| [`app.py`](app.py) | **Start here.** A small user directory: requests, handlers, the unit of work, and the container. |
| [`test_app.py`](test_app.py) | Dispatch plus all three lifetimes, as tests: `uv run pytest` → `7 passed`. |

## Small print

- This example depends on `pymediate[di]`, which pulls in `dependency-injector`. The
  integration lives in `pymediate.providers` — the core package never imports it.
- `DependencyInjectorServiceProvider` scans the container once, at construction. Build it
  from a finished container, not from a provider inside that same container.
- `GetUserHandler` never touches `unit_of_work` — it's read-only, and a unit of work only
  matters for the write it doesn't need to make.

## Where next

- [100-dependency-injection-sync](../100-dependency-injection-sync/) — the same three
  lifetimes on `pymediate.sync`.
- [120-custom-provider](../120-custom-provider/) — `ServiceProvider` is a Protocol; wire
  in your own container instead of `dependency-injector`.
- The docs: [dependency injection](https://pymediate.sina-al.uk/docs/guide/dependency-injection) ·
  [quick start](https://pymediate.sina-al.uk/docs/getting-started/quick-start).
