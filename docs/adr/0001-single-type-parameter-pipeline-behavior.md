# ADR 0001: Single Type Parameter for PipelineBehavior

**Status:** Proposed
**Date:** 2025-01-XX
**Author:** Claude
**Reviewers:** @saleyaasin

## Context

Currently, `PipelineBehavior` takes two generic type parameters:

```python
class PipelineBehavior[RequestT, ResponseT](ABC):
    @abstractmethod
    def __call__(
        self,
        request: RequestT,
        next: Callable[[], ResponseT],
    ) -> ResponseT:
        ...
```

**Usage example:**
```python
@dataclass
class CreateUserRequest(Request[UserResponse]):
    username: str

class LoggingBehavior(PipelineBehavior[CreateUserRequest, UserResponse]):
    def __call__(
        self,
        request: CreateUserRequest,
        next: Callable[[], UserResponse]
    ) -> UserResponse:
        print(f"Processing: {request.username}")
        return next()
```

### The Problem

The `ResponseT` type parameter is **redundant** because:

1. `CreateUserRequest` already declares its response type via `Request[UserResponse]`
2. The response type is **already known** from the request at class definition time
3. This creates **DRY violation** - we specify `UserResponse` twice:
   - Once in `Request[UserResponse]`
   - Again in `PipelineBehavior[CreateUserRequest, UserResponse]`
4. This opens the door for **type inconsistencies** - nothing prevents:
   ```python
   # Wrong but compiles!
   class BrokenBehavior(PipelineBehavior[CreateUserRequest, WrongResponse]):
       ...
   ```

### What We Want

Ideally, we'd like to write:

```python
class LoggingBehavior(PipelineBehavior[CreateUserRequest]):
    def __call__(
        self,
        request: CreateUserRequest,
        next: Callable[[], UserResponse]  # Inferred from CreateUserRequest!
    ) -> UserResponse:  # Also inferred!
        ...
```

## Investigation

### Python 3.12+ Features

Python 3.12 introduced:

1. **Default type parameters:**
   ```python
   T = TypeVar("T", default=int)
   class Box[T = int]: ...  # T defaults to int if not specified
   ```

2. **Bounded type parameters:**
   ```python
   T = TypeVar("T", bound=BaseClass)
   class Container[T: BaseClass]: ...  # T must be a subclass of BaseClass
   ```

3. **Combining both:**
   ```python
   T = TypeVar("T", bound=BaseClass, default=BaseClass)
   ```

### The Core Challenge

**Python's type system does NOT support extracting type parameters from generic base classes.**

We cannot do:
```python
# This doesn't exist in Python!
ResponseT = ExtractTypeParam[RequestT, 0]  # ❌ Not possible
```

Even with advanced typing features like:
- `TypeVarTuple`
- `ParamSpec`
- `Unpack`
- `typing.get_args()` (runtime only, not static typing)

**There is no static type system way to "extract" `UserResponse` from `CreateUserRequest` where `CreateUserRequest(Request[UserResponse])`.**

## Proposed Solutions

### Option 1: Single Type Parameter with Type: ignore (Pragmatic)

**Approach:** Use one type parameter but accept we must use `type: ignore` in implementation.

```python
TRequest = TypeVar("TRequest", bound=Request[Any])

class PipelineBehavior[TRequest: Request](ABC):
    @abstractmethod
    def __call__(
        self,
        request: TRequest,
        next: Callable[[], Any],  # Can't infer statically
    ) -> Any:  # Can't infer statically
        ...
```

**Usage:**
```python
class LoggingBehavior(PipelineBehavior[CreateUserRequest]):
    def __call__(
        self,
        request: CreateUserRequest,
        next: Callable[[], Any]  # type: ignore[override]
    ) -> Any:  # type: ignore[override]
        result: UserResponse = next()  # Manual type assertion
        return result
```

**Pros:**
- ✅ Simpler API - only specify request type once
- ✅ DRY - response type declared in one place (Request)
- ✅ Eliminates inconsistency risk

**Cons:**
- ❌ Loses type safety in behavior implementations
- ❌ Requires `type: ignore` comments everywhere
- ❌ No IDE autocomplete for response type
- ❌ Manual type assertions needed

**Verdict:** ❌ **REJECTED** - Type safety loss is too severe.

---

### Option 2: Runtime Type Extraction with Generic Alias (Hybrid)

**Approach:** Keep single type parameter but provide helper to extract response type at runtime.

```python
from typing import Any, get_args, get_origin

TRequest = TypeVar("TRequest", bound=Request[Any])

def get_response_type(request_type: type[Request]) -> type:
    """Extract ResponseT from Request[ResponseT] at runtime."""
    for base in getattr(request_type, "__orig_bases__", []):
        if get_origin(base) is Request:
            args = get_args(base)
            if args:
                return args[0]
    return Any

class PipelineBehavior[TRequest: Request](ABC):
    @abstractmethod
    def __call__(
        self,
        request: TRequest,
        next: Callable[[], Any],
    ) -> Any:
        ...
```

**Usage:**
```python
class LoggingBehavior(PipelineBehavior[CreateUserRequest]):
    def __call__(self, request, next):  # type: ignore[override]
        # Runtime knows UserResponse, static checker doesn't
        response = next()
        return response
```

**Pros:**
- ✅ Simpler API
- ✅ Runtime has full type information

**Cons:**
- ❌ Still no static type checking
- ❌ Doesn't solve the core problem

**Verdict:** ❌ **REJECTED** - Doesn't improve static typing.

---

### Option 3: Keep Two Type Parameters with Validation (Current + Enhancement)

**Approach:** Keep current design but add **static and runtime validation** that `ResponseT` matches what `RequestT` declares.

```python
from typing import Any, TypeVar, get_args, get_origin

TRequest = TypeVar("TRequest", bound=Request[Any])
TResponse = TypeVar("TResponse")

class PipelineBehavior[TRequest: Request, TResponse](ABC):
    """Pipeline behavior with validated type parameters.

    Both type parameters are required, but TResponse must match the response type
    declared by TRequest in Request[TResponse].
    """

    def __init_subclass__(cls, **kwargs):
        """Validate ResponseT matches RequestT's declared response type."""
        super().__init_subclass__(**kwargs)

        # Extract type parameters from PipelineBehavior[RequestT, ResponseT]
        if orig_bases := getattr(cls, "__orig_bases__", None):
            for base in orig_bases:
                if get_origin(base) is PipelineBehavior:
                    args = get_args(base)
                    if len(args) == 2:
                        request_type, response_type = args

                        # Get expected response type from Request[ResponseT]
                        expected_response = _get_request_response_type(request_type)

                        # Validate they match
                        if expected_response is not Any and response_type != expected_response:
                            raise TypeError(
                                f"{cls.__name__} declares response type {response_type.__name__}, "
                                f"but {request_type.__name__} expects {expected_response.__name__}"
                            )

    @abstractmethod
    def __call__(
        self,
        request: TRequest,
        next: Callable[[], TResponse],
    ) -> TResponse:
        ...

def _get_request_response_type(request_type: type) -> type:
    """Extract ResponseT from Request[ResponseT]."""
    # Similar to get_response_type() above
    ...
```

**Usage (Correct):**
```python
class LoggingBehavior(PipelineBehavior[CreateUserRequest, UserResponse]):
    # ✅ Validates at class definition time that UserResponse matches
    def __call__(self, request, next):
        return next()
```

**Usage (Wrong - caught at import time):**
```python
class BrokenBehavior(PipelineBehavior[CreateUserRequest, WrongResponse]):
    # ❌ Raises TypeError at class definition time!
    def __call__(self, request, next):
        return next()
```

**Pros:**
- ✅ **Full static type safety** preserved
- ✅ **Runtime validation** catches mismatches immediately
- ✅ Clear error messages at import time
- ✅ No behavior implementation changes needed
- ✅ Backward compatible with existing code
- ✅ IDE autocomplete fully works

**Cons:**
- ❌ Still requires specifying response type twice (but validated!)
- ❌ Slightly more verbose

**Verdict:** ✅ **RECOMMENDED** - Best balance of safety and usability.

---

### Option 4: Mypy Plugin (Advanced)

**Approach:** Write a mypy plugin to infer `ResponseT` from `RequestT`.

This would allow:
```python
class LoggingBehavior(PipelineBehavior[CreateUserRequest]):
    # Plugin infers UserResponse from CreateUserRequest
    ...
```

**Pros:**
- ✅ Perfect API
- ✅ Full static type checking

**Cons:**
- ❌ Requires mypy plugin (complex, maintenance burden)
- ❌ Doesn't work with other type checkers (pyright, pyre)
- ❌ IDE support varies
- ❌ Adds dependency on mypy-specific features

**Verdict:** ❌ **REJECTED** - Too complex, too narrow support.

## Decision

**RECOMMENDATION: Option 3 - Keep Two Type Parameters with Runtime Validation**

### Rationale

1. **Type safety is paramount** - PyMediate is a type-safe library, losing static typing would be a major regression
2. **Runtime validation adds safety** - Catches errors at import time, not runtime
3. **Backward compatible** - No breaking changes
4. **Best developer experience** - Full IDE support, clear error messages
5. **Pragmatic** - Works with all type checkers without special plugins

### What Changes

**Before (current):**
```python
class LoggingBehavior(PipelineBehavior[CreateUserRequest, UserResponse]):
    # No validation - could be wrong
    ...
```

**After (proposed):**
```python
class LoggingBehavior(PipelineBehavior[CreateUserRequest, UserResponse]):
    # ✅ Validates UserResponse matches CreateUserRequest's declared response type
    # ❌ Raises TypeError at import time if they don't match
    ...
```

### Implementation Plan

1. Add `__init_subclass__` to `PipelineBehavior` (sync and async)
2. Extract and validate response types match
3. Add comprehensive tests for validation
4. Update documentation with examples
5. Add migration guide (though it's backward compatible)

### Example Error Message

```python
class WrongBehavior(PipelineBehavior[CreateUserRequest, WrongResponse]):
    ...

# Raises at import time:
# TypeError: WrongBehavior declares response type WrongResponse,
# but CreateUserRequest expects UserResponse
```

## Alternatives Considered But Not Viable

### Why Not Single Type Parameter?

Python's type system fundamentally cannot extract generic type parameters for static type checking. While we could use:
- `typing.get_args()` - Runtime only
- Registry lookups - Runtime only
- Mypy plugins - Not portable

None provide **static type safety**, which is core to PyMediate's value proposition.

### Could This Change in Future Python Versions?

Possibly, but unlikely. This would require PEP-level changes to:
- Add type parameter extraction syntax
- Extend type checkers to support it
- Update typing stdlib

Even if proposed today, would take years to land and adopt.

## Migration Path

**No migration needed** - This is backward compatible enhancement.

Existing code continues to work identically, but gains additional safety.

## Consequences

### Positive

- ✅ Catches type mismatches at import time
- ✅ Better error messages
- ✅ Prevents subtle bugs
- ✅ No breaking changes
- ✅ Better DX - fails fast with clear errors

### Negative

- ⚠️ Still requires specifying both types (but validated)
- ⚠️ Slightly more complex implementation
- ⚠️ Minimal runtime overhead at class definition (one-time)

### Neutral

- 📝 Does not reduce verbosity
- 📝 Does not change API surface

## Open Questions

1. Should we provide a type alias helper to reduce verbosity?
   ```python
   # Helper to reduce typing:
   PB = PipelineBehavior  # Shorter alias

   class LoggingBehavior(PB[CreateUserRequest, UserResponse]):
       ...
   ```

2. Should validation be optional (opt-in via flag)?
   - Probably NO - always validate

3. Should we provide runtime type hints for response extraction?
   - Probably YES - utility function could help tooling

## References

- Python 3.12 PEP 695 (Type Parameter Syntax): https://peps.python.org/pep-0695/
- Python 3.12 PEP 696 (Default Type Parameters): https://peps.python.org/pep-0696/
- typing.get_args() documentation
- PyMediate Request.__init_subclass__ implementation

## Appendix: Type System Limitations

For reference, here's what Python's type system **cannot** do:

```python
# ❌ Cannot extract type from generic base
ResponseT = SomeExtractMagic[RequestT, 0]

# ❌ Cannot conditionally apply types
if RequestT extends Request[SomeResponseT]:
    use SomeResponseT

# ❌ Cannot perform type-level computation
ResponseT = RequestT.get_response_type()
```

These are fundamental limitations of Python's type system as of Python 3.13.
