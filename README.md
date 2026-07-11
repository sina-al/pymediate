<p align="center">
  <img src="https://github.com/sina-al/pymediate/blob/main/assets/logo.svg?raw=true" alt="PyMediate logo" width="400"><br><br>
  <b>A type-safe request mediator for Python 3.12+</b><br><br>

  <!-- Badges — row 1: the package (what/where), row 2: the guarantees (quality/security) -->
  <a href="https://pypi.org/project/pymediate/">
    <img src="https://img.shields.io/pypi/v/pymediate" alt="PyPI version">
  </a>
  <a href="https://pypi.org/project/pymediate/">
    <img src="https://img.shields.io/pypi/pyversions/pymediate" alt="Python versions">
  </a>
  <a href="https://opensource.org/licenses/MIT">
    <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="MIT License">
  </a>
  <a href="https://pymediate.sina-al.uk">
    <img src="https://img.shields.io/badge/docs-pymediate.sina--al.uk-blue" alt="Documentation">
  </a>
  <br>
  <a href="https://github.com/sina-al/pymediate/actions/workflows/test.yml">
    <img src="https://github.com/sina-al/pymediate/actions/workflows/test.yml/badge.svg" alt="Tests">
  </a>
  <a href="https://github.com/sina-al/pymediate/tree/python-coverage-comment-action-data">
    <img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/sina-al/pymediate/python-coverage-comment-action-data/endpoint.json" alt="Coverage">
  </a>
  <a href="https://mypy-lang.org/">
    <img src="https://img.shields.io/badge/mypy-strict-blue" alt="Checked with mypy (strict)">
  </a>
  <a href="https://scorecard.dev/viewer/?uri=github.com/sina-al/pymediate">
    <img src="https://api.scorecard.dev/projects/github.com/sina-al/pymediate/badge" alt="OpenSSF Scorecard">
  </a>
  <a href="https://github.com/sina-al/pymediate/attestations">
    <img src="https://slsa.dev/images/gh-badge-level2.svg" alt="SLSA Build Level 2">
  </a>
</p>

---

## Features

- **Type safe.** Full runtime validation with mypy support.
- **Events.** One-to-many `publish()` alongside one-to-one `send()` — same type-safe, validated-at-import design.
- **Async-first.** The top-level API is async; the full sync mirror lives in `pymediate.sync`.
- **DI ready.** Built-in `dependency-injector` integration.
- **Well tested.** Comprehensive test suite.

Wondering how this stacks up against other Python mediator libraries — and what `send()` and
`publish()` cost over direct calls? See [How it compares](https://pymediate.sina-al.uk/docs/comparison),
a source-level survey of the ecosystem plus a reproducible micro-benchmark you can run against
the latest release with `uv run https://pymediate.sina-al.uk/benchmark.py` (read it first, as
with any script from the network).

## Quick example

```python
import asyncio
from dataclasses import dataclass
from pymediate import Request, RequestHandler, Mediator, Services

# Define response and request as pure dataclasses
@dataclass
class UserCreated:
    user_id: int
    username: str

@dataclass
class CreateUser(Request[UserCreated]):
    username: str
    email: str

# RequestHandler automatically linked by type
class CreateUserHandler(RequestHandler[CreateUser]):
    async def __call__(self, req: CreateUser) -> UserCreated:
        return UserCreated(user_id=1, username=req.username)

# Set up and use
async def main():
    services = Services()
    services.add(CreateUserHandler())
    provider = services.provider()
    mediator = Mediator(provider)

    response = await mediator.send(CreateUser(username="alice", email="alice@example.com"))
    print(f"User {response.username} created with ID {response.user_id}")

asyncio.run(main())
```

### Sync support

Not every application runs an event loop. The `pymediate.sync` package is the
full sync mirror of the top-level API — the same names, with plain `def`
handlers and a blocking `send()`:

```python
from dataclasses import dataclass
from pymediate.sync import Request, RequestHandler, Mediator, Services

@dataclass
class UserCreated:
    user_id: int
    username: str

@dataclass
class CreateUser(Request[UserCreated]):
    username: str
    email: str

class CreateUserHandler(RequestHandler[CreateUser]):
    def __call__(self, req: CreateUser) -> UserCreated:
        return UserCreated(user_id=1, username=req.username)

services = Services()
services.add(CreateUserHandler())
provider = services.provider()
mediator = Mediator(provider)

response = mediator.send(CreateUser(username="alice", email="alice@example.com"))
print(f"User {response.username} created with ID {response.user_id}")
```

**Key differences for sync:**

- Import from `pymediate.sync` instead of `pymediate`.
- The handler's `__call__` method is a plain `def`.
- `mediator.send(...)` blocks and returns the response directly — no `await`.
- Shared names (`Request`, `Event`, `Services`, errors) are the same objects
  on both sides, so the two APIs mix freely in one codebase.

### Pipeline behaviors

PyMediate supports pipeline behaviors (middleware) that automatically wrap request processing for cross-cutting concerns like logging, validation, caching, and more:

```python
from pymediate import Request, PipelineBehavior

# Universal behavior - applies to all requests
class LoggingBehavior(PipelineBehavior[Request]):
    async def __call__(self, request, next):
        print(f"Handling: {type(request).__name__}")
        response = await next()
        print(f"Completed: {type(request).__name__}")
        return response

# Selective behavior - only applies to CreateUser requests
class ValidationBehavior(PipelineBehavior[CreateUser]):
    async def __call__(self, request, next):
        # Validate before processing
        if not request.username:
            raise ValueError("Username is required")
        return await next()

# Register behaviors and handlers
services = Services()
services.add(LoggingBehavior())       # Applied to all requests
services.add(ValidationBehavior())    # Only applied to CreateUser
services.add(CreateUserHandler())

mediator = Mediator(services.provider())

# Behaviors automatically wrap matching requests (inside an async context)
response = await mediator.send(CreateUser(username="alice", email="alice@example.com"))
# Output:
# Handling: CreateUser
# Completed: CreateUser
```

Behaviors can be **universal** (`PipelineBehavior[Request]`) or **selective** (`PipelineBehavior[SpecificRequest]`), applying only to matching request types or mixins. They're resolved per request and work with any `dependency-injector` provider lifetime — `Factory`, `Singleton`, or a scoped variant like `ContextLocalSingleton`. See the [Pipeline behaviors guide](https://pymediate.sina-al.uk/docs/guide/pipeline-behaviors) for more examples.

### Events

`send()` routes one request to its one handler. `publish()` is the one-to-many counterpart: announce a fact once, and every subscribed `EventHandler` reacts — the publisher never knows who's listening:

```python
from dataclasses import dataclass
from pymediate import Event, EventHandler, Mediator, Services

@dataclass
class OrderPlaced(Event):
    order_id: int

class SendConfirmation(EventHandler[OrderPlaced]):
    async def __call__(self, event: OrderPlaced) -> None:
        print(f"Confirming order {event.order_id}")

class UpdateAnalytics(EventHandler[OrderPlaced]):
    async def __call__(self, event: OrderPlaced) -> None:
        print(f"Recording order {event.order_id}")

services = Services()
services.add(SendConfirmation()).add(UpdateAnalytics())
mediator = Mediator(services.provider())

await mediator.publish(OrderPlaced(order_id=42))  # inside an async context
# Output:
# Confirming order 42
# Recording order 42
```

Handlers run concurrently via `asyncio.gather` (sequentially, in registration order, in the sync API), zero subscribers is a no-op, and a raising handler never stops the others — failures aggregate into an `ExceptionGroup`. See the [Events guide](https://pymediate.sina-al.uk/docs/guide/events).

## Installation

```bash
# Core package
pip install pymediate

# With dependency injection support
pip install pymediate[di]
```

## Documentation

**[📚 Full documentation](https://pymediate.sina-al.uk)**

- [Quick start](https://pymediate.sina-al.uk/docs/getting-started/quick-start)
- [User guide](https://pymediate.sina-al.uk/docs/guide/requests-responses)
- [Examples](https://pymediate.sina-al.uk/docs/examples/basic)
- [API reference](https://pymediate.sina-al.uk/docs/api/request)

## Development

### Quick start

```bash
# Clone and install
git clone https://github.com/sina-al/pymediate.git
cd pymediate
uv sync --all-extras --group test

# Optional: commit-time format/lint gate (same checks CI runs)
uvx pre-commit install

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

## Versioning

PyMediate follows [ZeroVer](https://0ver.org/) — the major version stays at `0` indefinitely,
with no planned 1.0. Expect the public API to keep evolving: a minor release (`0.X.0`) can
include breaking changes, while a patch release (`0.1.X`) is backward-compatible.

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT License — see [LICENSE](LICENSE) for details.
