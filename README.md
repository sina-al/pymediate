# PyMediate

[![Tests](https://github.com/sina-al/pymediate/workflows/Tests/badge.svg)](https://github.com/sina-al/pymediate/actions/workflows/test.yml)
[![Lint](https://github.com/sina-al/pymediate/workflows/Lint/badge.svg)](https://github.com/sina-al/pymediate/actions/workflows/lint.yml)
[![codecov](https://codecov.io/gh/sina-al/pymediate/branch/main/graph/badge.svg)](https://codecov.io/gh/sina-al/pymediate)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![PyPI version](https://badge.fury.io/py/pymediate.svg)](https://badge.fury.io/py/pymediate)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A type-safe mediator pattern implementation for Python 3.13+ with automatic type inference and runtime validation.

## Features

- **Type Safety**: Full runtime validation with mypy support
- **Zero Convention**: No naming conventions - uses type inspection
- **DI Ready**: Built-in dependency-injector integration
- **Dataclass Friendly**: Works seamlessly with `@dataclass` and Request[T] inheritance
- **Well Tested**: 71+ tests with 96%+ coverage

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

- Python 3.13+
- Optional: `dependency-injector>=4.41.0` for DI support

## Contributing

Contributions are welcome! Check the docs for guidelines.

## License

MIT License - see [LICENSE](LICENSE) for details.
