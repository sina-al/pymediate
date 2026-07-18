# 100-dependency-injection

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/sina-al/pymediate?devcontainer_path=.devcontainer%2F100-dependency-injection%2Fdevcontainer.json)

This example connects PyMediate to a
[`dependency-injector`](https://python-dependency-injector.ets-labs.org/) container through the
optional `pymediate[di]` extra. It demonstrates three provider lifetimes:

- `Factory`: create an instance each time the provider resolves it;
- `Singleton`: share one instance for the life of the container; and
- `ContextLocalSingleton`: share one instance in the current `contextvars` context until the
  provider is reset.

It assumes the application wiring introduced in [090-adapters](../090-adapters/) and replaces
manual service registration with a container-backed service provider.

## Run

Run these commands from `examples/100-dependency-injection`:

```bash
uv sync
uv run python app.py
```

```text
Registered: User(user_id=1, username='alice')
Unit of work: ['begin', "registered 'alice'", 'commit']
Registered: User(user_id=2, username='bob')
Unit of work: ['begin', "registered 'bob'", 'commit']
```

The repository retains both users because it is a `Singleton`. The unit-of-work log is reset
between the two operations, so Bob's log does not contain Alice's entry.

## Configure the container

```python
class AppContainer(containers.DeclarativeContainer):
    repository = providers.Singleton(UserRepository)
    unit_of_work = providers.ContextLocalSingleton(UnitOfWork)

    transaction_behavior = providers.Factory(
        TransactionLoggingBehavior,
        unit_of_work=unit_of_work,
    )
    register_user_handler = providers.Factory(
        RegisterUserHandler,
        repository=repository,
        unit_of_work=unit_of_work,
    )


container = AppContainer()
mediator = Mediator(DependencyInjectorServiceProvider(container))
user = await mediator.send(RegisterUser(username="alice"))
```

`DependencyInjectorServiceProvider` scans the completed container and indexes providers by the
concrete type they produce. The provider attribute names are not used for handler lookup.

The `Factory` providers create new handler and behavior instances when the mediator resolves
them. Those instances still receive the same singleton repository.

## Define and end a context-local scope

The handler and pipeline behavior independently resolve `unit_of_work`. Within one context,
the container returns the same instance, so their entries appear in order:

```python
class TransactionLoggingBehavior(PipelineBehavior[Request]):
    async def __call__(self, request, next):
        self._unit_of_work.record("begin")
        response = await next()
        self._unit_of_work.record("commit")
        return response
```

```text
['begin', "registered 'alice'", 'commit']
```

`ContextLocalSingleton` does not create or end web-request scopes automatically. The adapter
or middleware that owns the request boundary must reset the provider, including when dispatch
raises:

```python
try:
    response = await mediator.send(request)
finally:
    container.unit_of_work.reset()
```

Without that reset, later dispatches in the same context reuse the previous unit of work.

## Read the code

| File | What to read |
| --- | --- |
| [`app.py`](app.py) | **Start here.** Follow the providers in `AppContainer`, then `build_mediator` and the context-local reset in `main`. |
| [`test_app.py`](test_app.py) | See how the tests distinguish factory, singleton, and context-local provider behavior. |

Run the tests with `uv run pytest`; the expected result is `7 passed`.

## Details

- `pymediate[di]` installs `dependency-injector`. The optional integration is implemented in
  `pymediate.providers`; the core package does not import it.
- Construct `DependencyInjectorServiceProvider` after all required providers have been added to
  the container.
- `GetUserHandler` only reads the repository, so it does not receive a unit of work.

## Where next

- [110-testing](../110-testing/) — test handlers and mediator composition at separate
  boundaries.
- [100-dependency-injection-sync](../100-dependency-injection-sync/) — use the same container
  with `pymediate.sync`.
- [090-adapters](../090-adapters/) — review the application wiring that this example moves
  into a container.
- Read the [dependency-injection guide](https://pymediate.sina-al.uk/docs/guide/dependency-injection).
