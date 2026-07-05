# PyMediate

<p align="center">
  <strong>A type-safe mediator pattern implementation for Python 3.12+</strong>
</p>

<p align="center">
  <a href="https://github.com/sina-al/pymediate/actions"><img src="https://github.com/sina-al/pymediate/workflows/Tests/badge.svg" alt="Tests"></a>
  <a href="https://codecov.io/gh/sina-al/pymediate"><img src="https://codecov.io/gh/sina-al/pymediate/branch/main/graph/badge.svg" alt="Coverage"></a>
  <a href="https://pypi.org/project/pymediate"><img src="https://img.shields.io/pypi/v/pymediate.svg" alt="PyPI"></a>
  <a href="https://pypi.org/project/pymediate"><img src="https://img.shields.io/pypi/pyversions/pymediate.svg" alt="Python Versions"></a>
  <a href="https://github.com/sina-al/pymediate/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License"></a>
</p>

---

## What is PyMediate?

PyMediate is a modern, type-safe implementation of the [mediator pattern](https://refactoring.guru/design-patterns/mediator) for Python. It routes requests to their handlers without coupling the two together, so you get a clean, decoupled application.

## Key features

🎯 **Type-safe**
:   Runtime validation of handler signatures, with full static type checking support via mypy.

🔌 **Dependency injection ready**
:   Built-in support for `dependency-injector`, with automatic handler discovery.

🔄 **Async/await support**
:   First-class async handlers and mediators via `pymediate.aio`.

🧪 **Well tested**
:   135+ tests with 96%+ code coverage.

🚀 **Modern Python**
:   Built for Python 3.12+ using PEP 695 type parameter syntax.

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

# Create a handler - type inspection links it to CreateUser automatically
class CreateUserHandler(Handler[CreateUser]):
    def __call__(self, req: CreateUser) -> UserCreated:
        user_id = 1  # Simulated ID generation
        return UserCreated(user_id=user_id, username=req.username)

# Set up and use
services = Services()
services.add(CreateUserHandler())
mediator = Mediator(services.provider())

# Send a request - type-safe end-to-end
response = mediator.send(CreateUser(username="alice", email="alice@example.com"))
print(f"Created user {response.username} with ID {response.user_id}")
```

### Async support

PyMediate provides first-class async/await support:

```python
import asyncio
from pymediate import Services
from pymediate.aio import Handler, Mediator

class CreateUserHandler(Handler[CreateUser]):
    async def __call__(self, req: CreateUser) -> UserCreated:
        await database.save_user(req.username, req.email)
        return UserCreated(user_id=1, username=req.username)

async def main():
    services = Services()
    services.add(CreateUserHandler())
    mediator = Mediator(services.provider())
    response = await mediator.send(CreateUser(username="alice", email="alice@example.com"))
    print(f"Created user {response.username}")

asyncio.run(main())
```

[Learn more about async support →](examples/async.md)

## Why use the mediator pattern?

The mediator pattern helps you:

- **Decouple.** Handlers don't need to know about each other.
- **Test easily.** Mock the mediator to test consumers in isolation.
- **Follow CQRS.** Separate commands from queries naturally.
- **Scale cleanly.** Add new handlers without changing existing code.
- **Maintain more easily.** Keep a clear separation of concerns.

## What's different about PyMediate?

Unlike other mediator implementations, PyMediate:

1. **Uses type inspection, not naming conventions.** Handler providers can have any name.
2. **Infers the response type automatically.** Specify it once, in the request.
3. **Validates at class-definition time.** Catch errors before runtime, not after.
4. **Supports pure dataclasses.** Use `Request[T]` inheritance for clean, simple code.
5. **Provides first-class async/await support.** Async handlers and mediators via `pymediate.aio`.
6. **Works with modern Python.** Uses PEP 695 type parameters for cleaner generics.

## Installation

=== "Core package"

    ```bash
    pip install pymediate
    ```

=== "With DI support"

    ```bash
    pip install pymediate[di]
    ```

=== "Using uv"

    ```bash
    uv add pymediate
    # Or with DI
    uv add 'pymediate[di]'
    ```

## Next steps

<div class="grid cards" markdown>

-   :material-clock-fast:{ .lg .middle } __Quick start__

    ---

    Get up and running in 5 minutes.

    [:octicons-arrow-right-24: Quick start](getting-started/quick-start.md)

-   :material-book-open-variant:{ .lg .middle } __User guide__

    ---

    Learn PyMediate's concepts and patterns.

    [:octicons-arrow-right-24: User guide](guide/requests-responses.md)

-   :material-code-braces:{ .lg .middle } __Examples__

    ---

    See PyMediate in action with real examples.

    [:octicons-arrow-right-24: Examples](examples/basic.md)

-   :material-api:{ .lg .middle } __API reference__

    ---

    Detailed API documentation.

    [:octicons-arrow-right-24: API docs](api/request.md)

</div>

## Community and support

- **GitHub**: [sina-al/pymediate](https://github.com/sina-al/pymediate)
- **Issues**: [Report bugs](https://github.com/sina-al/pymediate/issues)
- **Discussions**: [Ask questions](https://github.com/sina-al/pymediate/discussions)

## License

PyMediate is released under the [MIT License](https://github.com/sina-al/pymediate/blob/main/LICENSE).
