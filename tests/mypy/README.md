# Mypy Type Safety Tests

Focused mypy tests that verify **type safety issues that ONLY mypy can catch** for pymediate users.

## Philosophy

These tests focus on compile-time type checking, not runtime behavior. If pymediate's runtime validation already catches an error, it doesn't need a mypy test.

**What belongs here:**
- Type inference through `mediator.send()`
- Type preservation through `resolver.resolve()`
- Response type correctness
- Type narrowing (Optional, Union)
- Complex nested type handling

**What doesn't belong here:**
- Handler signature validation (runtime `__init_subclass__` catches this)
- Request/Handler registration errors (runtime validation catches this)
- Anything testable with regular unit tests

## Test Coverage

### Valid Usage (9 snippets)

Tests verifying correct mypy type inference:

**Synchronous:**
- **basic_type_inference** - `mediator.send()` infers response type correctly
- **resolver_type_inference** - `resolver.resolve()` returns correctly typed handler
- **optional_fields** - Optional type narrowing with None checks
- **union_types** - Union type narrowing with isinstance
- **nested_types** - Complex nested types (List[T], Dict[K,V], nested dataclasses)
- **void_response** - None/void response handling

**Asynchronous:**
- **async_basic_type_inference** - Async `mediator.send()` with await
- **async_concurrent_requests** - Type inference with `asyncio.gather()`
- **async_handler_with_await** - Proper await usage in async handlers

### Error Detection (7 snippets)

Tests verifying mypy catches incorrect usage:

**Synchronous:**
- **wrong_response_attribute** - Accessing non-existent response attribute
- **wrong_response_type_assignment** - Assigning response to wrong type variable
- **optional_without_none_check** - Using Optional without None check
- **union_type_without_narrowing** - Using Union without type narrowing
- **mediator_send_wrong_expectation** - Expecting wrong response type from `send()`

**Asynchronous:**
- **async_missing_await_on_send** - Missing await on `mediator.send()`
- **async_wrong_response_attribute** - Accessing non-existent attribute on async response

## Running Tests

```bash
# Run all mypy tests
pytest tests/mypy/ -v

# Show coverage summary
pytest tests/mypy/test_user_type_safety.py::test_comprehensive_coverage_summary -v -s

# Run only valid usage tests
pytest tests/mypy/ -v -k "TestValidUsagePassesMypy"

# Run only error detection tests
pytest tests/mypy/ -v -k "TestInvalidUsageFailsMypy"
```

## Implementation

Uses the mypy API directly (not subprocess) for better performance:

```python
from mypy import api as mypy_api

def run_mypy_on_file(file_path: Path, strict: bool = True) -> tuple[int, str, str]:
    args = [str(file_path), "--show-error-codes", "--no-error-summary"]
    if strict:
        args.append("--strict")
    stdout, stderr, exit_code = mypy_api.run(args)
    return exit_code, stdout, stderr
```

## Test Structure

```
tests/mypy/
├── test_mypy.py                # Main test runner (uses mypy API)
├── snippets/
│   ├── valid/                  # Code that should pass mypy
│   └── errors/                 # Code that should fail mypy
└── README.md                   # This file
```

## Key Insights

### What Mypy Tests

- **Type inference**: Does `mediator.send(Request[T])` correctly infer type `T`?
- **Type safety**: Does mypy catch when you use a response incorrectly?
- **Type narrowing**: Does mypy understand Optional/Union handling?

### What Runtime Tests

- **Handler signatures**: `__init_subclass__` validates at class definition time
- **Registration errors**: Resolver validates handler-request compatibility
- **Missing handlers**: Caught when resolving/sending requests

Runtime validation is so comprehensive that many "type errors" are actually caught before your code even runs!

## Important Notes

### PEP 561 Compliance

The `src/pymediate/py.typed` marker file is **required** for mypy to recognize pymediate as typed. Without it, mypy treats the package as `Any` and skips type checking.

### Async/Await Support

PyMediate now includes first-class async support via `pymediate.aio`. The mypy tests cover both sync and async variants to ensure type safety in both environments.

## Statistics

- **Total mypy tests**: ~33 (all passing)
- **Valid patterns**: 9 (6 sync + 3 async)
- **Error scenarios**: 7 (5 sync + 2 async)
- **Test execution**: ~6 seconds
- **Mypy mode**: Strict (`--strict`)
- **Total project tests**: 127 tests total
  - 106 core functionality tests
  - 16 async functionality tests
  - 5 mypy snippet validation tests (not counted in pytest total)
