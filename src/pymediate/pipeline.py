"""Asynchronous pipeline behavior implementation for cross-cutting concerns.

This module provides async/await compatible pipeline behaviors for the mediator pattern.
Behaviors are fully asynchronous, allowing for async operations in the middleware chain.

See Also:
    - pymediate.sync.pipeline: Synchronous pipeline implementation
"""

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from typing import Any, ClassVar, TypeVar, get_args, get_origin

from .request import Request


def _resolve_request_type(cls: type) -> Any:
    """Find the type argument that fills ``PipelineBehavior``'s parameter for ``cls``.

    Walks intermediate generic bases (e.g. a reusable ``Behavior[RequestT]`` layer) and
    substitutes their type variables, so ``class Scoped(Behavior[Foo])`` resolves to ``Foo``.
    Returns the base's own parameter (a ``TypeVar``) when the behavior is left generic; the
    caller turns that into a universal match.
    """
    for base in getattr(cls, "__orig_bases__", ()):
        origin = get_origin(base)
        if origin is PipelineBehavior:
            args = get_args(base)
            return args[0] if args else Request
        if isinstance(origin, type) and issubclass(origin, PipelineBehavior):
            inner = _resolve_request_type(origin)
            if isinstance(inner, TypeVar):
                params = getattr(origin, "__type_params__", ()) or getattr(
                    origin, "__parameters__", ()
                )
                mapping = dict(zip(params, get_args(base), strict=False))
                return mapping.get(inner, inner)
            return inner
        if isinstance(base, type) and issubclass(base, PipelineBehavior):
            return _resolve_request_type(base)
    return Request


class PipelineBehavior[RequestT: Request[Any]](ABC):
    """Abstract base class for asynchronous pipeline behaviors that wrap request processing.

    An async pipeline behavior is middleware that sits between the mediator and the
    handler, allowing you to execute asynchronous logic before and after the handler
    processes the request.

    Behaviors can be selective - they only apply to specific request types or mixins.
    The type parameter indicates which requests this behavior applies to.

    Behaviors receive:
    - The request being processed (typed as RequestT)
    - A 'next' callable that represents the next step in the pipeline

    By awaiting next(), the behavior passes control to the next step. The behavior
    can execute code before awaiting next() (pre-processing), after awaiting next()
    (post-processing), or both.

    Type Parameters:
        RequestT: The request type (or mixin) this behavior applies to.
                  Can be Request (universal), a specific request class, or a mixin.

    Examples:
        Universal async behavior (applies to all requests):
            ```python
            from pymediate import PipelineBehavior, Request

            class AsyncLoggingBehavior(PipelineBehavior[Request]):
                async def __call__(
                    self,
                    request: Request,
                    next: Callable[[], Awaitable[Any]]
                ) -> Any:
                    await log_to_database(f"Handling: {type(request).__name__}")
                    response = await next()
                    await log_to_database(f"Handled: {type(request).__name__}")
                    return response
            ```

        Selective behavior for cacheable requests:
            ```python
            class CacheableMixin:
                cache_key: str
                ttl: int

            class CachingBehavior(PipelineBehavior[CacheableMixin]):
                def __init__(self, cache: AsyncCache):
                    self.cache = cache

                async def __call__(
                    self,
                    request: CacheableMixin,
                    next: Callable[[], Awaitable[Any]]
                ) -> Any:
                    # Check cache
                    cached = await self.cache.get(request.cache_key)
                    if cached is not None:
                        return cached

                    # Execute and cache
                    response = await next()
                    await self.cache.set(request.cache_key, response, ttl=request.ttl)
                    return response
            ```

        Specific request type with transaction:
            ```python
            class TransactionBehavior(PipelineBehavior[CreateOrderRequest]):
                def __init__(self, db: AsyncDatabase):
                    self.db = db

                async def __call__(
                    self,
                    request: CreateOrderRequest,
                    next: Callable[[], Awaitable[Any]]
                ) -> Any:
                    async with self.db.transaction():
                        return await next()
            ```

    Attributes:
        apply_to_subclasses: If True (default), applies to subclasses of RequestT.
                            If False, only applies to exact type match.

    Note:
        The response type is not statically known because selective behaviors can
        apply to requests with different response types. If you need response type
        safety, manually annotate in your implementation:

            ```python
            async def __call__(self, request: MyRequest, next) -> MyResponse:
                result: MyResponse = await next()  # Manual type assertion
                return result
            ```

        For synchronous behaviors, use `pymediate.sync.PipelineBehavior` instead.

    See Also:
        - Mediator.send: Discovers applicable behaviors and runs them
          around the handler.
        - should_apply: Override to customize behavior selection logic
        - pymediate.sync.PipelineBehavior: Sync version
    """

    apply_to_subclasses: bool = True

    # Resolved once per subclass in __init_subclass__; the base class is universal.
    __request_type__: ClassVar[Any] = Request
    __match_type__: ClassVar[Any] = Request

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Resolve and cache the behavior's request type when a subclass is defined."""
        super().__init_subclass__(**kwargs)
        request_type = _resolve_request_type(cls)
        # A behavior left generic (registered without narrowing, e.g. a reusable base used
        # directly) resolves to a TypeVar - fall back to its bound so it matches universally
        # instead of raising in should_apply's isinstance() check.
        if isinstance(request_type, TypeVar):
            bound = request_type.__bound__
            request_type = bound if bound is not None else Request
        cls.__request_type__ = request_type
        # A subscripted generic like Request[Any] has no isinstance()/type() meaning of
        # its own - match against its origin (Request) instead.
        origin = get_origin(request_type)
        cls.__match_type__ = origin if origin is not None else request_type

    @classmethod
    def should_apply(cls, request: Request[Any]) -> bool:
        """Determine if this behavior should apply to the given request.

        Default implementation uses isinstance() check against the type parameter.
        Override for custom matching logic.

        Args:
            request: The request to check

        Returns:
            True if this behavior should apply to the request

        Examples:
            Custom matching logic:
                ```python
                class RateLimitBehavior(PipelineBehavior[Request]):
                    @classmethod
                    def should_apply(cls, request: Request) -> bool:
                        # Only apply to non-admin users
                        return not getattr(request, 'is_admin', False)
                ```

            Multiple type matching:
                ```python
                class ValidationBehavior(PipelineBehavior[Request]):
                    @classmethod
                    def should_apply(cls, request: Request) -> bool:
                        return isinstance(request, (CreateRequest, UpdateRequest))
                ```
        """
        match_type = cls.__match_type__
        if match_type is Request:
            return True  # Universal behavior

        if cls.apply_to_subclasses:
            return isinstance(request, match_type)
        return type(request) is match_type

    @abstractmethod
    async def __call__(
        self,
        request: RequestT,
        next: Callable[[], Awaitable[Any]],
    ) -> Any:
        """Execute the behavior's async logic and await next to continue the pipeline.

        Args:
            request: The request being processed (typed as RequestT)
            next: Async callable that invokes the next behavior or handler in the chain

        Returns:
            The response from the handler (type not statically known)

        Note:
            This method should await next() to continue the pipeline execution.
            Code before next() runs before the handler, code after runs after.

            The response type is Any because selective behaviors can apply to
            requests with different response types. If you need type safety,
            manually annotate the return type in your implementation.
        """
        ...


__all__ = [
    "PipelineBehavior",
]
