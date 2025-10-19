# PyMediate

<p align="center">
  <strong>A type-safe mediator pattern implementation for Python 3.13+</strong>
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

PyMediate is a modern, type-safe implementation of the [Mediator Pattern](https://refactoring.guru/design-patterns/mediator) for Python. It helps you build clean, decoupled applications by routing requests to their appropriate handlers without tight coupling.

## Key Features

🎯 **Type-Safe**
:   Runtime validation of handler signatures with full static type checking support via mypy

⚡ **Zero Convention**
:   No naming conventions required - uses type inspection to match handlers with requests

🔌 **Dependency Injection Ready**
:   Built-in support for dependency-injector with automatic handler discovery

📦 **Dataclass Friendly**
:   Works seamlessly with Python dataclasses using Request[T] inheritance

🧪 **Well Tested**
:   71+ comprehensive tests with 96%+ code coverage

🚀 **Modern Python**
:   Built for Python 3.13+ using PEP 695 type parameter syntax

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

# Create a handler - automatically linked by type inspection!
class CreateUserHandler(Handler[CreateUser]):
    def __call__(self, req: CreateUser) -> UserCreated:
        user_id = 1  # Simulated ID generation
        return UserCreated(user_id=user_id, username=req.username)

# Set up and use
resolver = SimpleResolver()
resolver.register(CreateUser, CreateUserHandler())
mediator = Mediator(resolver)

# Send request - type-safe end-to-end
response = mediator.send(CreateUser(username="alice", email="alice@example.com"))
print(f"Created user {response.username} with ID {response.user_id}")
```

## Why Use the Mediator Pattern?

The mediator pattern helps you:

- **Decouple** components - handlers don't need to know about each other
- **Test easily** - mock the mediator for testing consumers
- **Follow CQRS** - separate commands from queries naturally
- **Scale cleanly** - add new handlers without changing existing code
- **Maintain** code better - clear separation of concerns

## What's Different About PyMediate?

Unlike other mediator implementations, PyMediate:

1. **Uses type inspection instead of naming conventions** - your handler providers can have ANY name
2. **Provides automatic response type inference** - specify response type once in the request
3. **Validates at class definition time** - catch errors before runtime
4. **Supports pure dataclasses** - use Request[T] inheritance for clean, simple code
5. **Works with modern Python** - uses PEP 695 type parameters for cleaner generics

## Installation

=== "Core Package"

    ```bash
    pip install pymediate
    ```

=== "With DI Support"

    ```bash
    pip install pymediate[di]
    ```

=== "Using uv"

    ```bash
    uv add pymediate
    # Or with DI
    uv add 'pymediate[di]'
    ```

## Next Steps

<div class="grid cards" markdown>

-   :material-clock-fast:{ .lg .middle } __Quick Start__

    ---

    Get up and running in 5 minutes

    [:octicons-arrow-right-24: Quick Start](getting-started/quick-start.md)

-   :material-book-open-variant:{ .lg .middle } __User Guide__

    ---

    Learn PyMediate concepts and patterns

    [:octicons-arrow-right-24: User Guide](guide/requests-responses.md)

-   :material-code-braces:{ .lg .middle } __Examples__

    ---

    See PyMediate in action with real examples

    [:octicons-arrow-right-24: Examples](examples/basic.md)

-   :material-api:{ .lg .middle } __API Reference__

    ---

    Detailed API documentation

    [:octicons-arrow-right-24: API Docs](api/request.md)

</div>

## Community & Support

- **GitHub**: [sina-al/pymediate](https://github.com/sina-al/pymediate)
- **Issues**: [Report bugs](https://github.com/sina-al/pymediate/issues)
- **Discussions**: [Ask questions](https://github.com/sina-al/pymediate/discussions)

## License

PyMediate is released under the [MIT License](https://github.com/sina-al/pymediate/blob/main/LICENSE).
