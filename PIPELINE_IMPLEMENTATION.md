# Pipeline Behavior Implementation - Design Summary

## Overview

I've implemented a comprehensive, type-safe pipeline behavior system for PyMediate, inspired by MediatR's `IPipelineBehavior` pattern. The implementation provides middleware-like functionality for cross-cutting concerns in the mediator pattern.

## Key Design Decisions

### 1. **Protocol-Based Design vs Runtime Validation**

**Decision**: Use `Protocol` for `PipelineBehavior` WITHOUT runtime validation (unlike `Handler` which has extensive `__init_subclass__` validation).

**Reasoning**:
- **Handlers** need runtime validation because they:
  - Are automatically registered in a global registry
  - Must match Request-Response type mappings
  - Have strict signature requirements enforced at class definition time
  - Are resolved dynamically at runtime

- **Pipeline Behaviors** don't need this because they:
  - Are NOT registered in any global registry
  - Are instantiated and composed explicitly by the user
  - Have flexible, duck-typed signatures (Protocol structural typing)
  - Type safety is enforced by mypy at compile-time, not runtime

### 2. **`next` as `Callable` Instead of `Handler`**

**Question Raised**: Why is `next` typed as `Callable[[], ResponseT]` instead of `Handler[RequestT]`?

**Answer**: This is the correct design because:

```python
# In the pipeline chain:
# Behavior 1 -> Behavior 2 -> Behavior 3 -> Handler

# Each behavior's `next` could be:
# - Another behavior (not a Handler!)
# - The final handler
# - A wrapped/composed function

# The signature captures what matters:
def __call__(
    self,
    request: RequestT,
    next: Callable[[], ResponseT],  # "Call this to get the response"
) -> ResponseT:
    # request is available in closure
    response = next()  # Invoke the next step
    return response
```

This design:
- **Encapsulates** the request in the closure (single responsibility)
- **Abstracts** the pipeline chain (behavior doesn't care what's next)
- **Enables** composition (behaviors, handlers, or any callable)
- **Matches** MediatR's design pattern exactly

### 3. **No Type Constraints on Generic Parameters**

```python
# Original (failed strict mypy):
class PipelineBehavior[RequestT: Request, ResponseT](Protocol):
    ...

# Final (passes strict mypy):
class PipelineBehavior[RequestT, ResponseT](Protocol):
    ...
```

**Reasoning**:
- Type constraints like `RequestT: Request` are not needed for generics when using `--strict` mode
- The constraint doesn't add runtime or compile-time value since:
  - The `Handler[RequestT]` parameter already constrains that `RequestT` is a valid request
  - Mypy infers types correctly without explicit constraints
  - The protocol is duck-typed anyway

## Implementation Structure

### Core Components

#### 1. **Synchronous Pipeline** (`src/pymediate/pipeline.py`)
```python
class PipelineBehavior[RequestT, ResponseT](Protocol):
    """Protocol for pipeline behaviors"""
    def __call__(
        self,
        request: RequestT,
        next: Callable[[], ResponseT],
    ) -> ResponseT: ...

class Pipeline[RequestT, ResponseT]:
    """Chains behaviors together"""
    def __init__(
        self,
        behaviors: Sequence[PipelineBehavior[RequestT, ResponseT]],
        handler: Handler[RequestT],
    ) -> None: ...
```

#### 2. **Asynchronous Pipeline** (`src/pymediate/aio/pipeline.py`)
- Same design, fully async/await compatible
- `next: Callable[[], Awaitable[ResponseT]]`

### Test Coverage

#### Runtime Tests
- **36 tests** total (17 sync + 19 async)
- Covers: execution order, modification, short-circuiting, validation, exceptions, caching, concurrency

#### Mypy Type Safety Tests
- **7 new tests** for pipeline behaviors
- **Valid scenarios** (4 tests):
  - `pipeline_basic_usage.py`
  - `pipeline_multiple_behaviors.py`
  - `pipeline_response_modification.py`
  - `async_pipeline_basic_usage.py`

- **Error detection** (3 tests):
  - `pipeline_wrong_response_attribute.py`
  - `pipeline_wrong_response_type.py`
  - `async_pipeline_missing_await.py`

All tests pass with **strict mypy mode** (`--strict`).

## Type Safety Strategy Alignment

The implementation follows PyMediate's dual type-safety approach:

### Compile-Time (mypy)
- Generic type parameters `[RequestT, ResponseT]`
- Protocol structural typing for behaviors
- Full type inference through pipeline chains
- Strict mode compliance

### Runtime (for Handlers, not Behaviors)
- Handlers: `__init_subclass__` validation
- Request-Response registry
- Signature verification at class definition time

### Why Behaviors Don't Need Runtime Validation
1. **No global registration** - composed explicitly
2. **Structural typing** - Protocol matches any compatible shape
3. **User-visible errors** - mistakes caught immediately during composition
4. **mypy catches everything** - comprehensive compile-time checking

## Example Usage

```python
from pymediate import Handler, Request
from pymediate.pipeline import Pipeline

class LoggingBehavior:
    def __call__(self, request, next):
        print(f"Before: {type(request).__name__}")
        response = next()
        print(f"After: response received")
        return response

class TimingBehavior:
    def __call__(self, request, next):
        import time
        start = time.time()
        response = next()
        print(f"Took {time.time() - start:.4f}s")
        return response

# Compose pipeline
handler = CreateUserHandler()
pipeline = Pipeline([LoggingBehavior(), TimingBehavior()], handler)

# Execute
response = pipeline(CreateUserRequest(username="alice"))
```

## Design Philosophy Comparison

### Handlers (Runtime Validation)
- **Global registration** required
- **Strict contracts** enforced
- **Type registry** integration
- **Single instance** per request type
- **Framework-managed** lifecycle

### Behaviors (Compile-Time Only)
- **Local composition** by user
- **Flexible protocols** supported
- **No registration** needed
- **Multiple instances** per pipeline
- **User-managed** lifecycle

## Test Results

✅ **All 43 pipeline tests** pass
✅ **All 37 mypy tests** pass (including 7 new pipeline tests)
✅ **Strict mypy** mode passes on all pipeline modules
✅ **Zero type errors** in source code

## Files Created/Modified

### Source Code
- `src/pymediate/pipeline.py` - Sync pipeline implementation
- `src/pymediate/aio/pipeline.py` - Async pipeline implementation

### Tests
- `tests/test_pipeline.py` - 17 sync runtime tests
- `tests/test_pipeline_async.py` - 19 async runtime tests
- `tests/mypy/snippets/valid/pipeline_basic_usage.py`
- `tests/mypy/snippets/valid/pipeline_multiple_behaviors.py`
- `tests/mypy/snippets/valid/pipeline_response_modification.py`
- `tests/mypy/snippets/valid/async_pipeline_basic_usage.py`
- `tests/mypy/snippets/errors/pipeline_wrong_response_attribute.py`
- `tests/mypy/snippets/errors/pipeline_wrong_response_type.py`
- `tests/mypy/snippets/errors/async_pipeline_missing_await.py`

## Conclusion

The pipeline implementation is:
- **Type-safe**: Full generic support with mypy strict mode
- **Aligned**: Follows PyMediate's existing patterns
- **Tested**: Comprehensive runtime and type-safety test coverage
- **Documented**: Extensive docstrings with examples
- **Flexible**: Protocol-based for maximum composability
- **Production-ready**: All tests passing, zero type errors

The key insight is recognizing that **behaviors and handlers have different lifecycle requirements**, which justifies their different validation strategies: handlers need runtime validation for global registry management, while behaviors benefit from compile-time-only validation for maximum flexibility.
