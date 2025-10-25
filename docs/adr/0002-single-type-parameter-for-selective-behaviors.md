# ADR 0002: Single Type Parameter for Selective Pipeline Behaviors

**Status:** Proposed
**Date:** 2025-01-XX
**Author:** Claude
**Context:** Supersedes ADR-0001 based on future vision for selective behaviors
**Reviewers:** @saleyaasin

## Context

### Future Vision: Selective Behaviors Based on Request Mixins

The long-term goal is to support **selective behaviors** that only apply to specific request types or mixins:

```python
from dataclasses import dataclass

@dataclass
class Principal:
    user_id: str
    roles: list[str]
    is_authenticated: bool

class AuthMixin:
    """Mixin for requests that require authentication."""
    principal: Principal

class CacheableMixin:
    """Mixin for requests that can be cached."""
    cache_key: str
    ttl: int = 300

# Request with authentication
class CreateOrderRequest(Request[OrderResponse], AuthMixin):
    product_id: str
    quantity: int
    principal: Principal  # From AuthMixin

# Request with caching
class GetUserRequest(Request[UserResponse], CacheableMixin):
    user_id: str
    cache_key: str
    ttl: int = 600
```

### Desired Behavior Pattern

```python
class AuthorizationBehavior(PipelineBehavior[AuthMixin]):
    """Only applies to requests with AuthMixin."""
    def __call__(self, request: AuthMixin, next):
        if not request.principal.is_authenticated:
            raise Unauthorized("Authentication required")
        return next()

class CachingBehavior(PipelineBehavior[CacheableMixin]):
    """Only applies to requests with CacheableMixin."""
    def __call__(self, request: CacheableMixin, next):
        cached = cache.get(request.cache_key)
        if cached:
            return cached
        result = next()
        cache.set(request.cache_key, result, ttl=request.ttl)
        return result
```

### Key Insight

When behaviors are **selective**, the priorities shift:

| Aspect | Current Importance | Future Importance |
|--------|-------------------|-------------------|
| Request type matching | Medium | **CRITICAL** |
| Request type safety | High | **CRITICAL** |
| Response type safety | High | **Medium** |
| Verbosity reduction | Low | **HIGH** |

**Why response type is less critical:**
- Behaviors that check mixins don't care about response type
- They pass through whatever the handler returns
- Type safety at behavior level is less important than type safety at handler level

## Proposed Solution: Single Type Parameter with Request Focus

### Design

```python
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any, TypeVar

from .request import Request

TRequest = TypeVar("TRequest", bound=Request)

class PipelineBehavior[TRequest: Request](ABC):
    """Pipeline behavior that can selectively apply based on request type.

    Type Parameters:
        TRequest: The request type (or mixin) this behavior applies to.
                  Can be a Request subclass, a mixin class, or Request itself.

    The behavior will automatically apply to:
    - Exact matches of TRequest
    - Subclasses of TRequest (if apply_to_subclasses=True)

    Examples:
        Universal behavior (applies to all requests):
            ```python
            class LoggingBehavior(PipelineBehavior[Request]):
                def __call__(self, request: Request, next: Callable[[], Any]) -> Any:
                    print(f"Processing: {type(request).__name__}")
                    return next()
            ```

        Selective behavior for authenticated requests:
            ```python
            class AuthMixin:
                principal: Principal

            class AuthBehavior(PipelineBehavior[AuthMixin]):
                def __call__(self, request: AuthMixin, next: Callable[[], Any]) -> Any:
                    if not request.principal.is_authenticated:
                        raise Unauthorized()
                    return next()
            ```

        Specific request type:
            ```python
            class CreateOrderBehavior(PipelineBehavior[CreateOrderRequest]):
                def __call__(self, request: CreateOrderRequest, next: Callable[[], Any]) -> Any:
                    # Only applies to CreateOrderRequest
                    validate_order(request)
                    return next()
            ```
    """

    # Class attribute: whether to apply to subclasses of TRequest
    apply_to_subclasses: bool = True

    @classmethod
    def should_apply(cls, request: Request) -> bool:
        """Determine if this behavior should apply to the given request.

        Default implementation uses isinstance() check against the type parameter.
        Override for custom matching logic.

        Args:
            request: The request to check

        Returns:
            True if this behavior should apply to the request

        Examples:
            Custom matching:
                ```python
                class ConditionalBehavior(PipelineBehavior[Request]):
                    @classmethod
                    def should_apply(cls, request: Request) -> bool:
                        # Only apply during business hours
                        return 9 <= datetime.now().hour < 17
                ```
        """
        request_type = cls.__get_request_type__()
        if request_type is Request:
            return True  # Universal behavior
        return isinstance(request, request_type)

    @classmethod
    def __get_request_type__(cls) -> type:
        """Extract TRequest from PipelineBehavior[TRequest]."""
        from typing import get_args, get_origin

        for base in getattr(cls, "__orig_bases__", []):
            if get_origin(base) is PipelineBehavior:
                args = get_args(base)
                if args:
                    return args[0]
        return Request  # Fallback to universal

    @abstractmethod
    def __call__(
        self,
        request: TRequest,
        next: Callable[[], Any],
    ) -> Any:
        """Execute the behavior's logic.

        Args:
            request: The request being processed (typed as TRequest)
            next: Callable that invokes the next behavior or handler

        Returns:
            The response from the handler (type unknown at compile time)

        Note:
            The response type is not statically known because:
            1. Selective behaviors don't care about response type
            2. Different request subclasses have different response types
            3. Runtime filtering makes static typing impossible

            For behaviors that need response type safety, manually annotate:
                ```python
                def __call__(self, request: MyRequest, next) -> MyResponse:
                    result: MyResponse = next()  # Manual assertion
                    return result
                ```
        """
        ...
```

### Mediator Integration

```python
class Mediator:
    def send[ResponseT](self, request: Request[ResponseT]) -> ResponseT:
        # Resolve all behaviors
        all_behaviors = self._service_provider.resolve_all(PipelineBehavior)

        # Filter to only applicable behaviors
        applicable_behaviors = [
            b for b in all_behaviors
            if b.should_apply(request)
        ]

        # If no behaviors, call handler directly
        if not applicable_behaviors:
            return handler(request)

        # Build pipeline with filtered behaviors
        pipeline = Pipeline(applicable_behaviors, handler)
        return pipeline(request)
```

### Example Usage Scenarios

#### 1. Authorization Behavior (Mixin-Based)

```python
from dataclasses import dataclass

@dataclass
class Principal:
    user_id: str
    is_authenticated: bool
    roles: set[str]

class AuthMixin:
    """Mixin for requests requiring authentication."""
    principal: Principal

class AuthorizationBehavior(PipelineBehavior[AuthMixin]):
    """Applies only to requests with AuthMixin."""

    def __call__(self, request: AuthMixin, next: Callable[[], Any]) -> Any:
        # Type checker knows request.principal exists!
        if not request.principal.is_authenticated:
            raise Unauthorized("User must be authenticated")

        return next()

class RequireRoleBehavior(PipelineBehavior[AuthMixin]):
    """Requires specific role."""

    def __init__(self, required_role: str):
        self.required_role = required_role

    def __call__(self, request: AuthMixin, next: Callable[[], Any]) -> Any:
        if self.required_role not in request.principal.roles:
            raise Forbidden(f"Role '{self.required_role}' required")

        return next()

# Request that gets these behaviors
@dataclass
class CreateOrderRequest(Request[OrderResponse], AuthMixin):
    product_id: str
    quantity: int
    principal: Principal  # From AuthMixin

# Request that doesn't get these behaviors
@dataclass
class GetProductRequest(Request[ProductResponse]):
    product_id: str
    # No AuthMixin - auth behaviors won't apply!
```

#### 2. Caching Behavior (Mixin-Based)

```python
class CacheableMixin:
    cache_key: str
    ttl: int = 300

class CachingBehavior(PipelineBehavior[CacheableMixin]):
    def __init__(self, cache: Cache):
        self.cache = cache

    def __call__(self, request: CacheableMixin, next: Callable[[], Any]) -> Any:
        # Check cache
        cached = self.cache.get(request.cache_key)
        if cached is not None:
            return cached

        # Execute and cache
        result = next()
        self.cache.set(request.cache_key, result, ttl=request.ttl)
        return result

@dataclass
class GetUserRequest(Request[UserResponse], CacheableMixin):
    user_id: str
    cache_key: str  # From CacheableMixin
    ttl: int = 600
```

#### 3. Universal Behavior (Applies to All)

```python
class LoggingBehavior(PipelineBehavior[Request]):
    """Applies to ALL requests."""

    def __call__(self, request: Request, next: Callable[[], Any]) -> Any:
        logger.info(f"Processing {type(request).__name__}")
        try:
            result = next()
            logger.info(f"Completed {type(request).__name__}")
            return result
        except Exception as e:
            logger.error(f"Failed {type(request).__name__}: {e}")
            raise
```

#### 4. Specific Request Type

```python
class CreateOrderValidationBehavior(PipelineBehavior[CreateOrderRequest]):
    """Only applies to CreateOrderRequest."""

    def __call__(self, request: CreateOrderRequest, next: Callable[[], Any]) -> Any:
        if request.quantity <= 0:
            raise ValueError("Quantity must be positive")
        if request.quantity > 1000:
            raise ValueError("Quantity exceeds maximum")
        return next()
```

#### 5. Custom Matching Logic

```python
class BusinessHoursBehavior(PipelineBehavior[Request]):
    """Only applies during business hours."""

    @classmethod
    def should_apply(cls, request: Request) -> bool:
        from datetime import datetime
        hour = datetime.now().hour
        return 9 <= hour < 17

    def __call__(self, request: Request, next: Callable[[], Any]) -> Any:
        # Log that this request happened during business hours
        log_business_hours_request(request)
        return next()
```

## Pros and Cons

### Pros

✅ **Simpler API** - Only one type parameter to specify
✅ **Matches future vision** - Designed for selective behavior application
✅ **Request type safety** - Full type checking for request access
✅ **Mixin support** - Perfect for mixin-based request categorization
✅ **Flexibility** - `should_apply()` allows custom matching logic
✅ **Less verbosity** - Don't specify response type when you don't care
✅ **Clear semantics** - Type parameter indicates "applies to"

### Cons

❌ **No response type safety** - Response is `Any` at behavior level
❌ **Manual type assertions** - If you care about response, must annotate manually
❌ **Potential confusion** - Developers might expect response type to be inferred

### Mitigations for Cons

1. **Documentation** - Clearly explain response type is not statically checked
2. **Convention** - Behaviors typically don't modify responses, just pass through
3. **Manual annotation** - When needed, easy to add:
   ```python
   def __call__(self, request: MyRequest, next) -> MyResponse:
       result: MyResponse = next()
       # Now result is typed as MyResponse
       return result
   ```

## Comparison: Current vs Proposed

### Current (Two Type Parameters)

```python
# Must specify both
class AuthBehavior(PipelineBehavior[AuthMixin, Any]):  # What's the response? Any?
    def __call__(
        self,
        request: AuthMixin,
        next: Callable[[], Any]  # Still Any!
    ) -> Any:  # Still Any!
        ...
```

**Problem:** If response is always `Any` for selective behaviors, why specify it?

### Proposed (One Type Parameter)

```python
# Only specify what matters
class AuthBehavior(PipelineBehavior[AuthMixin]):
    def __call__(
        self,
        request: AuthMixin,  # ✅ Typed!
        next: Callable[[], Any]  # ✅ Honest about response
    ) -> Any:  # ✅ Clear we don't know
        ...
```

## Migration Path

This would be a **breaking change** requiring major version bump.

### Step 1: Deprecation (v2.x)

Support both signatures:
```python
# Old way (deprecated)
class Behavior(PipelineBehavior[Request, Response]):
    ...

# New way
class Behavior(PipelineBehavior[Request]):
    ...
```

### Step 2: Migration (v3.0)

Only support single parameter:
```python
class Behavior(PipelineBehavior[Request]):
    ...
```

### Migration Tool

Provide codemod script:
```python
# Before
PipelineBehavior[CreateUserRequest, UserResponse]

# After
PipelineBehavior[CreateUserRequest]
```

## Decision

**RECOMMENDATION: Adopt Single Type Parameter Design**

### Rationale

1. **Aligns with future vision** - Selective behaviors don't care about response type
2. **Simpler API** - Less verbose, clearer intent
3. **Request type is what matters** - For mixin matching and filtering
4. **Response type safety is handler's job** - Not behavior's job
5. **Honest about limitations** - `Any` response is honest vs. lie that we can infer it

### When to Use Which

| Use Case | Type Parameter | Reasoning |
|----------|----------------|-----------|
| Universal behavior | `PipelineBehavior[Request]` | Applies to all requests |
| Mixin-based selection | `PipelineBehavior[AuthMixin]` | Only requests with this mixin |
| Specific request | `PipelineBehavior[CreateOrderRequest]` | Only this request type |
| Custom selection | Override `should_apply()` | Complex matching logic |

## Open Questions

1. **Should we support multiple type parameters for OR matching?**
   ```python
   class Behavior(PipelineBehavior[AuthMixin | CacheableMixin]):
       # Applies to either
       ...
   ```
   - Probably NO - use `should_apply()` for complex logic

2. **Should `apply_to_subclasses` be configurable per behavior?**
   ```python
   class ExactMatchBehavior(PipelineBehavior[CreateOrderRequest]):
       apply_to_subclasses = False  # Only CreateOrderRequest, not subclasses
   ```
   - Probably YES - useful for very specific behaviors

3. **Should we provide type utilities for response annotation?**
   ```python
   from pymediate.typing import ResponseOf

   def __call__(self, request: MyRequest, next) -> ResponseOf[MyRequest]:
       # ResponseOf[MyRequest] = MyResponse (extracted at runtime)
       ...
   ```
   - Probably NO - doesn't help static type checking

## Implementation Checklist

- [ ] Update `PipelineBehavior` base class signature
- [ ] Add `should_apply()` class method
- [ ] Add `__get_request_type__()` helper
- [ ] Update `Mediator.send()` to filter behaviors
- [ ] Update `Pipeline` to work with filtered behaviors
- [ ] Add comprehensive tests for selective application
- [ ] Update all documentation and examples
- [ ] Provide migration guide
- [ ] Update ADR-0001 status to "Superseded"

## Conclusion

The single type parameter design is **superior** given the future vision of selective behaviors based on request mixins. It's simpler, clearer, and matches the actual usage pattern better than trying to maintain response type safety that's impossible to achieve statically.

The trade-off (losing response type safety at behavior level) is acceptable because:
1. Handlers still have full response type safety
2. Behaviors rarely care about specific response types
3. Manual annotation is easy when needed
4. The alternative (two parameters) doesn't actually solve the problem
