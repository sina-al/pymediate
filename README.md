<p align="center">
  <img src="https://github.com/sina-al/pymediate/blob/main/assets/logo.svg?raw=true" alt="PyMediate logo" width="400"><br><br>
  <b>A type-safe request mediator for Python 3.12+</b><br><br>

  <!-- Badges -->
  <a href="https://github.com/sina-al/pymediate/actions/workflows/test.yml">
    <img src="https://github.com/sina-al/pymediate/actions/workflows/test.yml/badge.svg" alt="Tests">
  </a>
  <a href="https://github.com/sina-al/pymediate/actions/workflows/code-quality.yml">
    <img src="https://github.com/sina-al/pymediate/actions/workflows/code-quality.yml/badge.svg" alt="Code Quality">
  </a>
  <a href="https://www.python.org/downloads/">
    <img src="https://img.shields.io/badge/python-3.12+-blue.svg" alt="Python 3.12+">
  </a>
  <a href="https://badge.fury.io/py/pymediate">
    <img src="https://badge.fury.io/py/pymediate.svg" alt="PyPI version">
  </a>
  <a href="https://opensource.org/licenses/MIT">
    <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="MIT License">
  </a>
</p>

---

## Features

- **Type safe.** Full runtime validation with mypy support.
- **Async/await support.** First-class async handlers and mediators via `pymediate.aio`.
- **DI ready.** Built-in `dependency-injector` integration.
- **Well tested.** Comprehensive test suite.

## Quick example

```python
from dataclasses import dataclass
from pymediate import Request, Handler, Mediator, Services

# Define response and request as pure dataclasses
@dataclass
class UserCreated:
    user_id: int
    username: str

@dataclass
class CreateUser(Request[UserCreated]):
    username: str
    email: str

# Handler automatically linked by type
class CreateUserHandler(Handler[CreateUser]):
    def __call__(self, req: CreateUser) -> UserCreated:
        return UserCreated(user_id=1, username=req.username)

# Set up and use
services = Services()
services.add(CreateUserHandler())
provider = services.provider()
mediator = Mediator(provider)

response = mediator.send(CreateUser(username="alice", email="alice@example.com"))
print(f"User {response.username} created with ID {response.user_id}")
```

### Async support

PyMediate provides first-class async/await support through the `pymediate.aio` package:

```python
import asyncio
from dataclasses import dataclass
from pymediate import Request, Services
from pymediate.aio import Handler, Mediator

@dataclass
class UserCreated:
    user_id: int
    username: str

@dataclass
class CreateUser(Request[UserCreated]):
    username: str
    email: str

class CreateUserHandler(Handler[CreateUser]):
    async def __call__(self, req: CreateUser) -> UserCreated:
        # Perform async operations
        await asyncio.sleep(0.1)  # Simulate async database call
        return UserCreated(user_id=1, username=req.username)

async def main():
    services = Services()
    services.add(CreateUserHandler())
    provider = services.provider()
    mediator = Mediator(provider)

    response = await mediator.send(CreateUser(username="alice", email="alice@example.com"))
    print(f"User {response.username} created with ID {response.user_id}")

asyncio.run(main())
```

**Key differences for async:**

- Import from `pymediate.aio` instead of `pymediate`.
- The handler's `__call__` method must be `async def`.
- Use `await mediator.send(...)` instead of `mediator.send(...)`.
- Supports concurrent request handling with `asyncio.gather()`.

### Pipeline behaviors

PyMediate supports pipeline behaviors (middleware) that automatically wrap request processing for cross-cutting concerns like logging, validation, caching, and more:

```python
from pymediate import Request, PipelineBehavior

# Universal behavior - applies to all requests
class LoggingBehavior(PipelineBehavior[Request]):
    def __call__(self, request, next):
        print(f"Handling: {type(request).__name__}")
        response = next()
        print(f"Completed: {type(request).__name__}")
        return response

# Selective behavior - only applies to CreateUser requests
class ValidationBehavior(PipelineBehavior[CreateUser]):
    def __call__(self, request, next):
        # Validate before processing
        if not request.username:
            raise ValueError("Username is required")
        return next()

# Register behaviors and handlers
services = Services()
services.add(LoggingBehavior())       # Applied to all requests
services.add(ValidationBehavior())    # Only applied to CreateUser
services.add(CreateUserHandler())

mediator = Mediator(services.provider())

# Behaviors automatically wrap matching requests
response = mediator.send(CreateUser(username="alice", email="alice@example.com"))
# Output:
# Handling: CreateUser
# Completed: CreateUser
```

Behaviors can be **universal** (`PipelineBehavior[Request]`) or **selective** (`PipelineBehavior[SpecificRequest]`), applying only to matching request types or mixins. They're resolved per request and work with any `dependency-injector` provider lifetime — `Factory`, `Singleton`, or a scoped variant like `ContextLocalSingleton`. See the [Pipeline behaviors guide](https://sina-al.github.io/pymediate/guide/pipeline-behaviors/) for more examples.

## Installation

```bash
# Core package
pip install pymediate

# With dependency injection support
pip install pymediate[di]
```

## Documentation

**[📚 Full documentation](https://sina-al.github.io/pymediate/)**

- [Quick start](https://sina-al.github.io/pymediate/getting-started/quick-start/)
- [User guide](https://sina-al.github.io/pymediate/guide/requests-responses/)
- [Examples](https://sina-al.github.io/pymediate/examples/basic/)
- [API reference](https://sina-al.github.io/pymediate/api/request/)

## Development

### Quick start

```bash
# Clone and install
git clone https://github.com/sina-al/pymediate.git
cd pymediate
uv sync --all-extras --group test

# Run tests
poe test

# Run all checks
poe check:all

# See all available tasks
poe
```

### Available commands

PyMediate uses [Poe the Poet](https://poethepoet.natn.io/) for task running. Run `poe` to see all commands, or check [`tasks.toml`](tasks.toml).

> **Note:** `uv sync` alone only installs the default `dev` dependency group (ruff, mypy,
> poethepoet). Test dependencies (pytest and friends) live in the separate `test` group and
> won't be installed unless you pass `--group test` (or `--all-groups`) — otherwise `poe test`
> fails with `Failed to spawn: pytest`.

## Requirements

- Python 3.12+.
- Optional: `dependency-injector>=4.41.0` for DI support.

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT License — see [LICENSE](LICENSE) for details.
