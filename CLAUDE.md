# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PyMediate is a type-safe mediator pattern implementation for Python 3.12+. It provides compile-time and runtime type safety through automatic type inference and validation using Python's generic type system and metaclass hooks.

## Development Commands

This project uses [Poe the Poet](https://poethepoet.natn.io/) for task running via `uv run poe <task>`. All commands assume you're using `uv` as the package manager.

### Essential Commands

```bash
# Install dependencies
uv sync --all-extras

# Run all tests
uv run poe test

# Run tests with coverage
uv run poe test:cov

# Run single test file
uv run pytest tests/test_handler.py

# Run specific test function
uv run pytest tests/test_handler.py::test_handler_validates_return_type

# Type checking (source only)
uv run poe type

# Type checking (source + tests)
uv run poe type:all

# Linting and formatting
uv run poe lint              # Check only
uv run poe lint:fix          # Auto-fix issues
uv run poe format            # Format code
uv run poe fix               # Fix linting + format (full cleanup)

# All quality checks
uv run poe check             # Type + lint + format check
uv run poe check:all         # All checks + tests with coverage

# Documentation
uv run poe docs:serve        # Start dev server with live reload
uv run poe docs:build        # Build documentation site

# Quick workflows
uv run poe dev               # Fix code + run fast tests
uv run poe pr                # Prepare for PR (fix + all checks)
```

### Running Specific Tests

```bash
# Fast test run (exit on first failure)
uv run poe test:fast

# Run only failed tests from last run
uv run poe test:failed

# Run tests matching pattern
uv run pytest -k "dataclass"

# Run tests with verbose output
uv run poe test:verbose
```

## Architecture

### Core Design Philosophy

1. **Type Inference Over Explicit Declaration**: Users specify `Request[ResponseType]` once, and the framework infers all other types automatically
2. **Fail Fast with Clear Messages**: Validation happens at **class definition time** (import time) using `__init_subclass__`, not at runtime
3. **Protocol-Based Extensibility**: Uses `Protocol` for interfaces (e.g., `ServiceProvider`), not abstract base classes
4. **Sync/Async Separation**: Complete separation between synchronous (`pymediate`) and asynchronous (`pymediate.aio`) implementations

### Module Structure

```
src/pymediate/
├── request.py              # Request base class with generic response type
├── handler.py              # Synchronous Handler base class
├── mediator.py             # Synchronous Mediator
├── service.py              # Services and ServiceProvider protocol
├── pipeline.py             # Pipeline behaviors (middleware)
├── errors.py               # All exception types
├── _internal/              # Internal implementation details
│   ├── registry.py         # Global request→response type mapping
│   ├── handler.py          # HandlerBaseMixin with validation logic
│   └── mediator.py         # MediatorMixin shared between sync/async
├── aio/                    # Async variants (parallel structure)
│   ├── handler.py          # Async Handler base class
│   ├── mediator.py         # Async Mediator
│   └── pipeline.py         # Async pipeline behaviors
└── providers/              # Service provider implementations
    └── di_resolver.py      # DependencyInjectorServiceProvider
```

### Key Components Flow

**Request Processing:**
1. User defines `CreateUserRequest(Request[UserResponse])`
2. `Request.__init_subclass__` extracts `UserResponse` and stores in registry
3. User defines `CreateUserHandler(Handler[CreateUserRequest])`
4. `Handler.__init_subclass__` validates `__call__` signature matches types
5. At runtime, `mediator.send(request)` looks up handler type from registry
6. Mediator uses `ServiceProvider` to get handler instance
7. Handler is invoked and response is returned

**Registry System:**
The `_internal/registry.py` maintains a global mapping:
- `request_type -> response_type` (populated by Request.__init_subclass__)
- `request_type -> handler_type` (populated by Handler.__init_subclass__)

This enables the mediator to route requests without requiring manual registration.

### Sync vs Async

PyMediate provides **parallel implementations** for sync and async:

- **Synchronous**: Import from `pymediate` - handlers are regular functions
- **Asynchronous**: Import from `pymediate.aio` - handlers use `async def`

Key differences:
- Sync: `Handler.__call__(request) -> Response`
- Async: `Handler.__call__(request) -> Response` (must be `async def`)
- Sync: `mediator.send(request)` returns response
- Async: `await mediator.send(request)` returns response

The `_internal/` module contains shared validation logic via mixins (`HandlerBaseMixin`, `MediatorMixin`).

### Pipeline Behaviors (Middleware)

Pipeline behaviors wrap request processing for cross-cutting concerns:

```python
# Sync behavior
class LoggingBehavior:
    def __call__(
        self,
        request: RequestT,
        next: Callable[[], ResponseT],
    ) -> ResponseT:
        print(f"Before: {request}")
        response = next()
        print(f"After: {response}")
        return response

# Async behavior
class AsyncLoggingBehavior:
    async def __call__(
        self,
        request: RequestT,
        next: Callable[[], Awaitable[ResponseT]],
    ) -> ResponseT:
        print(f"Before: {request}")
        response = await next()
        print(f"After: {response}")
        return response
```

Behaviors form a chain where each wraps the next:
```
Request → Behavior 1 → Behavior 2 → Behavior 3 → Handler → Response
```

Behaviors use **Protocol-based typing** (structural typing), not runtime validation like handlers.

### Validation Strategy

**Handler Validation (at class definition time):**
- Uses `__init_subclass__` hook
- Inspects `__call__` method signature using `inspect` module
- Validates: parameter type matches `RequestT`, return type matches `ResponseT`
- Raises clear errors with actionable messages if validation fails
- Happens when module is imported, not when handler is called

**Request Validation (at class definition time):**
- Uses `__init_subclass__` hook
- Extracts `ResponseT` from `Request[ResponseT]` using `__orig_bases__`
- Registers mapping in global registry
- No runtime overhead

**Why this matters:** Errors are caught during development (import time), not production (runtime).

## Testing Conventions

### Function-Based Tests (Required)

Per `CONTRIBUTING.md`, use **function-based tests**, not class-based:

```python
# ✅ Good - function-based
def test_handler_validates_return_type():
    """Test that handler validates return type at class definition."""
    with pytest.raises(TypeError):
        class BadHandler(Handler[TestRequest]):
            def __call__(self, request: TestRequest) -> str:  # Wrong type!
                return "hello"

# ❌ Bad - class-based (avoid)
class TestHandler:
    def test_validation(self):
        ...
```

**Important:** Classes prefixed with `Test` will be collected by pytest as test classes. If you need classes in tests (e.g., `TestResponse`, `TestRequest`), rename them to `SampleResponse`, `SampleRequest`, etc.

### Type Annotations in Tests

When using strict mypy (`poe type:all`), pipeline and complex generic variables need explicit type annotations:

```python
# Required for mypy --strict
pipeline: Pipeline[SampleRequest, SampleResponse] = Pipeline([behavior], handler)
```

### Test Coverage Requirements

- **Minimum:** 95% coverage
- **Target:** 100% on core modules (`handler.py`, `mediator.py`, `request.py`, `service.py`)
- Run: `uv run poe test:cov`

### Mypy Snippet Tests

Type checking tests live in `tests/mypy/snippets/`:
- `valid/` - Code that should pass mypy
- `errors/` - Code that should fail mypy (with `type: ignore` comments)

These are automatically tested by `poe type:all` which excludes `errors/` directory.

## Code Style Requirements

### Type Hints (Mandatory)

All public APIs must have complete type hints:

```python
# ✅ Good
def send[ResponseT](self, request: Request[ResponseT]) -> ResponseT:
    """Send a request and return its response."""
    ...

# ❌ Bad - missing type hints
def send(self, request):
    ...
```

### Docstrings (Mandatory)

All public classes, methods, and functions need Google-style docstrings:

```python
def resolve(self, request_class: type[RequestType]) -> Handler[RequestType]:
    """Resolve a request class to its handler.

    Args:
        request_class: The request class to resolve

    Returns:
        Handler instance for the request

    Raises:
        ValueError: If no handler is registered for the request class
    """
    ...
```

### Import Organization

Group imports in this order:
1. Standard library
2. Third-party packages
3. Local modules

```python
import inspect
from typing import Any, Protocol

from dependency_injector import containers

from pymediate.handler import Handler
```

### Naming Conventions

- **Classes**: `PascalCase` (e.g., `RequestHandler`, `SimpleResolver`)
- **Functions/Methods**: `snake_case` (e.g., `send_request`, `validate_handler`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `_REQUEST_REGISTRY`)
- **Private members**: Prefix with `_` (e.g., `_resolver`)

### Line Length

Maximum 100 characters per line (configured in ruff.toml). Break long lines:

```python
# ✅ Good
pipeline: Pipeline[SampleRequest, SampleResponse] = Pipeline(
    [logging, timing, validation, multiplier], handler
)

# ❌ Bad - over 100 characters
pipeline: Pipeline[SampleRequest, SampleResponse] = Pipeline([logging, timing, validation, multiplier], handler)
```

## Common Development Patterns

### Adding a New Feature

1. Read the relevant documentation in `docs/`
2. Understand the validation strategy (class definition time vs runtime)
3. Implement with full type hints and docstrings
4. Write function-based tests
5. Add mypy snippet tests if adding new type checking behavior
6. Update documentation in `docs/` (concepts, guide, examples, API reference)
7. Run `uv run poe pr` to verify all checks pass

### Adding Async Support for a Feature

If you add a sync feature, you likely need to add an async variant:

1. Implement in `src/pymediate/feature.py`
2. Implement async variant in `src/pymediate/aio/feature.py`
3. Test both in `tests/test_feature.py` and `tests/test_feature_async.py`
4. Document both in the same doc files (use separate sections)

### Working with the Registry

The registry is in `src/pymediate/_internal/registry.py`. It's populated automatically via `__init_subclass__` hooks. You rarely need to interact with it directly, but understanding it helps debug issues:

```python
# Registry structure (simplified)
_request_response_types: dict[type, type] = {}  # Request -> Response
_request_handler_types: dict[type, type] = {}   # Request -> Handler
```

### Validation Error Messages

When validation fails, provide clear, actionable error messages:

```python
# ✅ Good - specific and actionable
raise InvalidHandlerSignatureError(
    f"{handler_class.__name__}.__call__ must return {expected_response.__name__}, "
    f"not {actual_return.__name__}. Update your handler's return type annotation."
)

# ❌ Bad - vague
raise ValueError("Invalid handler")
```

## Documentation Structure

Documentation lives in `docs/` and uses MkDocs with Material theme:

```
docs/
├── getting-started/
│   ├── quick-start.md
│   └── concepts.md
├── guide/
│   ├── requests-responses.md
│   ├── handlers.md
│   ├── mediator.md
│   └── pipeline-behaviors.md
├── examples/
│   ├── basic.md
│   └── pipeline-behaviors.md
└── api/
    ├── request.md
    ├── handler.md
    └── pipeline.md
```

When adding a new feature:
1. Add concept explanation in `docs/getting-started/concepts.md`
2. Add detailed guide in `docs/guide/`
3. Add working examples in `docs/examples/`
4. Add API reference in `docs/api/` using mkdocstrings
5. Update navigation in `mkdocs.yml`

## Troubleshooting

### "Cannot collect test class" Warning

If pytest warns about collecting classes starting with `Test`:
- Rename: `TestResponse` → `SampleResponse`
- Rename: `TestRequest` → `SampleRequest`

### Mypy "Need type annotation" Error

With `--strict` mode, generic variables need explicit annotations:

```python
# Add type annotation
pipeline: Pipeline[SampleRequest, SampleResponse] = Pipeline([behavior], handler)
```

### Line Too Long (E501)

Break long lines across multiple lines:

```python
pipeline: Pipeline[SampleRequest, SampleResponse] = Pipeline(
    [behavior1, behavior2], handler
)
```

### Import Errors with Async

Make sure you're importing from the correct module:
- Sync: `from pymediate import Handler, Mediator`
- Async: `from pymediate.aio import Handler, Mediator`
- Request and Services are always from `pymediate` (shared between sync/async)
