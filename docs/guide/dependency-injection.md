# Dependency Injection

PyMediate includes built-in support for `dependency-injector`, making it easy to wire up handlers with their dependencies.

## Installation

```bash
pip install pymediate[di]
```

## Basic Usage

The `DependencyInjectorServiceProvider` uses **type inspection** - no naming conventions required!

```python
from dependency_injector import containers, providers
from pymediate import Handler, Mediator, DependencyInjectorServiceProvider

class AppContainer(containers.DeclarativeContainer):
    database = providers.Singleton(Database)

    # Provider name can be ANYTHING!
    user_service = providers.Factory(CreateUserHandler, database=database)

    __self__ = providers.Self()
    mediator = providers.Singleton(
        Mediator,
        services=providers.Singleton(DependencyInjectorServiceProvider, container=__self__)
    )
```

## Key Features

- **No Naming Conventions**: Provider names don't matter
- **Automatic Discovery**: Uses `isinstance()` and type inspection
- **O(1) Lookups**: Pre-built cache for fast resolution
- **Works with Factory and Singleton**: Both provider types supported

See full examples in the [Examples section](../examples/basic.md).
