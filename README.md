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

- **Type Safety**: Full runtime validation with mypy support
- **Zero Convention**: No naming conventions - uses type inspection
- **Async/Await Support**: First-class async handlers and mediators via `pymediate.aio`
- **DI Ready**: Built-in dependency-injector integration
- **Dataclass Friendly**: Works seamlessly with `@dataclass` and Request[T] inheritance
- **Well Tested**: 135+ tests with 96%+ coverage

## Quick Example

```python
from dataclasses import dataclass
from pymediate import Request, Handler, Mediator, SimpleResolver

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
resolver = SimpleResolver()
resolver.register(CreateUser, CreateUserHandler())
mediator = Mediator(resolver)

response = mediator.send(CreateUser(username="alice", email="alice@example.com"))
print(f"User {response.username} created with ID {response.user_id}")
```

### Async Support

PyMediate provides first-class async/await support through the `pymediate.aio` package:

```python
import asyncio
from dataclasses import dataclass
from pymediate import Request, SimpleResolver
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
    resolver = SimpleResolver()
    resolver.register(CreateUser, CreateUserHandler())
    mediator = Mediator(resolver)

    response = await mediator.send(CreateUser(username="alice", email="alice@example.com"))
    print(f"User {response.username} created with ID {response.user_id}")

asyncio.run(main())
```

**Key differences for async:**
- Import from `pymediate.aio` instead of `pymediate`
- Handler's `__call__` method must be `async def`
- Use `await mediator.send(...)` instead of `mediator.send(...)`
- Supports concurrent request handling with `asyncio.gather()`

## Installation

```bash
# Core package
pip install pymediate

# With dependency injection support
pip install pymediate[di]
```

## Documentation

**[📚 Full Documentation](https://sina-al.github.io/pymediate/)**

- [Quick Start](https://sina-al.github.io/pymediate/getting-started/quick-start/)
- [User Guide](https://sina-al.github.io/pymediate/guide/requests-responses/)
- [Examples](https://sina-al.github.io/pymediate/examples/basic/)
- [API Reference](https://sina-al.github.io/pymediate/api/request/)

## Development

### Quick Start

```bash
# Clone and install
git clone https://github.com/sina-al/pymediate.git
cd pymediate
uv sync --all-extras

# Run tests
poe test

# Run all checks
poe check:all

# See all available tasks
poe
```

### Available Commands

PyMediate uses [Poe the Poet](https://poethepoet.natn.io/) for task running. Run `poe` to see all commands, or check [`tasks.toml`](tasks.toml).

## Requirements

- Python 3.12+
- Optional: `dependency-injector>=4.41.0` for DI support

## Contributing

Contributions are welcome! Check the docs for guidelines.

## License

MIT License - see [LICENSE](LICENSE) for details.
