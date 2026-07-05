# Dependency injection

PyMediate includes built-in support for [`dependency-injector`](https://python-dependency-injector.ets-labs.org/), so you can wire up handlers with their dependencies through a DI container instead of constructing them by hand.

Install the optional extra to use it.

```bash
pip install pymediate[di]
```

See [Installation](../getting-started/installation.md) for other package managers, and the [troubleshooting guide](../advanced/troubleshooting.md#dependencyinjectorserviceprovider-not-available) if the import fails.

## Basic setup

`DependencyInjectorServiceProvider` wraps a `dependency-injector` container and implements PyMediate's `ServiceProvider` [protocol](https://docs.python.org/3/library/typing.html#typing.Protocol), so you can hand it to `Mediator` in place of `Services.provider()`. It resolves handlers by their concrete type using type inspection — the provider's name in the container doesn't matter.

```python
from dependency_injector import containers, providers
from pymediate import Handler, Mediator
from pymediate.providers import DependencyInjectorServiceProvider

class AppContainer(containers.DeclarativeContainer):
    database = providers.Singleton(Database)

    # The provider name can be anything - PyMediate matches by type, not by name
    user_service = providers.Factory(CreateUserHandler, database=database)
```

```python
container = AppContainer()
provider = DependencyInjectorServiceProvider(container)
mediator = Mediator(provider)

response = mediator.send(CreateUserRequest(username="alice", email="alice@example.com"))
```

Build `DependencyInjectorServiceProvider` from a container you've already constructed, not from a provider declared inside that same container. Registering it as one of the container's own providers (for example, via a `providers.Self()` reference) makes the container try to resolve it while still scanning itself, which recurses until Python's recursion limit is hit.

## Factory vs. Singleton providers

`DependencyInjectorServiceProvider` works with either provider type — use whichever matches the handler's intended lifetime.

```python
class AppContainer(containers.DeclarativeContainer):
    database = providers.Singleton(Database)

    # Factory: a new handler instance is created on every resolution
    create_user_handler = providers.Factory(CreateUserHandler, database=database)

    # Singleton: the same handler instance is reused across every resolution
    metrics_handler = providers.Singleton(RecordMetricsHandler, database=database)
```

Most handlers should be `Factory` unless they're genuinely stateless and safe to share.

## Testing with a DI container

Override providers for tests the same way you would with any `dependency-injector` container.

```python
def test_create_user_with_container():
    container = AppContainer()
    container.database.override(providers.Singleton(InMemoryDatabase))

    provider = DependencyInjectorServiceProvider(container)
    mediator = Mediator(provider)
    response = mediator.send(CreateUserRequest(username="alice", email="alice@example.com"))

    assert response.username == "alice"
```

If you don't need the container at all for a given test, resolve the handler directly instead — see [Testing without frameworks](requests-responses.md#testing-without-frameworks).


## See also

- [Handlers](handlers.md) - Writing the handlers you'll wire up here.
- [Pipeline behaviors: DI container integration](pipeline-behaviors.md#di-container-integration) - Registering behaviors through the same container.
- [Troubleshooting](../advanced/troubleshooting.md) - Common DI setup issues.
