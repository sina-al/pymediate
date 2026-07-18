# with-dependency-injector

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/sina-al/pymediate?devcontainer_path=.devcontainer%2Fwith-dependency-injector%2Fdevcontainer.json)

The basic examples wire handlers by hand with `Services`. This one hands the wiring to a
real DI container instead —
[dependency-injector](https://python-dependency-injector.ets-labs.org/), via PyMediate's
optional **`di` extra**. Same mediator, different composition root.

## Run it

```bash
cd examples/with-dependency-injector
uv sync
uv run python app.py
```

```text
Registered: User(user_id=1, username='alice')
Found: alice
```

## The idea, in ten lines

Declare handlers and their dependencies in a container, wrap the container so PyMediate
can read it, and hand that to the mediator:

```python
class AppContainer(containers.DeclarativeContainer):
    repository = providers.Singleton(UserRepository)
    register_user_handler = providers.Factory(RegisterUserHandler, repository=repository)
    get_user_handler = providers.Factory(GetUserHandler, repository=repository)

mediator = Mediator(DependencyInjectorServiceProvider(AppContainer()))
user = mediator.send(RegisterUser(username="alice"))     # typed: user is a User
```

PyMediate never sees the wiring — only the finished container. Provider lifetimes are
respected: `Factory` handlers are rebuilt per dispatch, and every one of them receives
the same `Singleton` repository.

## The files

| File | What it is |
| --- | --- |
| [`app.py`](app.py) | **Start here.** A small user directory: requests, handlers, and the container. |
| [`test_app.py`](test_app.py) | Dispatch plus the lifetime semantics, as tests: `uv run pytest` → `5 passed`. |

## Small print

- This example depends on `pymediate[di]`, which pulls in `dependency-injector`. The
  integration lives in `pymediate.providers` — the core package never imports it.
- `DependencyInjectorServiceProvider` indexes declared output types without constructing
  providers. It also follows nested `providers.Container` declarations in order.
- The mediator may be built outside the container, as here, or composed inside it with
  Dependency Injector's `providers.Self()` pattern.

## Where next

- [adapters-sync](../adapters-sync/) — a bigger composition-root story: one core, three
  frameworks.
- The docs: [dependency injection](https://pymediate.sina-al.uk/docs/guide/dependency-injection) ·
  [quick start](https://pymediate.sina-al.uk/docs/getting-started/quick-start).
