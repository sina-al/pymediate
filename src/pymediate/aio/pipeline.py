"""Asynchronous pipeline behavior implementation for cross-cutting concerns.

This module provides async/await compatible pipeline behaviors for the mediator pattern.
All behaviors and the pipeline itself are fully asynchronous, allowing for async operations
in the middleware chain.

See Also:
    - pymediate.pipeline: Synchronous pipeline implementation
"""

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable, Sequence
from typing import Any, get_args, get_origin

from ..request import Request
from .handler import Handler


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
            from pymediate import Request
            from pymediate.aio.pipeline import PipelineBehavior

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

        For synchronous behaviors, use `pymediate.pipeline.PipelineBehavior` instead.

    See Also:
        - Pipeline: Chains multiple async behaviors together
        - should_apply: Override to customize behavior selection logic
        - pymediate.pipeline.PipelineBehavior: Sync version
    """

    apply_to_subclasses: bool = True

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
        request_type = cls.__get_request_type__()
        if request_type is Request:
            return True  # Universal behavior

        # Handle subscripted generics (e.g., Request[Any])
        # Extract the origin type (Request) and use that for isinstance check
        origin = get_origin(request_type)
        if origin is not None:
            # If request_type is a subscripted generic like Request[Any],
            # check against the origin (Request)
            return isinstance(request, origin)

        # Non-generic type (e.g., CreateUserRequest or a mixin)
        return isinstance(request, request_type)

    @classmethod
    def __get_request_type__(cls) -> type:
        """Extract RequestT from PipelineBehavior[RequestT].

        Returns:
            The request type this behavior is parameterized with,
            or Request if no type parameter specified.
        """
        for base in getattr(cls, "__orig_bases__", []):
            if get_origin(base) is PipelineBehavior:
                args = get_args(base)
                if args:
                    return args[0]  # type: ignore[no-any-return]
        return Request  # Fallback to universal  # type: ignore[return-value]

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


class Pipeline[RequestT, ResponseT]:
    """Chains multiple async pipeline behaviors together to form a request processing pipeline.

    The async Pipeline class combines multiple async behaviors and an async handler into
    a single async callable that processes requests through the behavior chain before
    reaching the final handler.

    Behaviors are executed in the order provided, with each behavior wrapping the next
    one, ultimately wrapping the final handler.

    Type Parameters:
        RequestT: The request type (must extend Request)
        ResponseT: The response type returned by the handler

    Attributes:
        _behaviors: Sequence of async behaviors to execute in order
        _handler: The final async handler that processes the request

    Examples:
        Basic async pipeline:
            ```python
            from pymediate import Request
            from pymediate.aio import Handler
            from pymediate.aio.pipeline import Pipeline

            class UserCreatedResponse:
                def __init__(self, user_id: int):
                    self.user_id = user_id

            class CreateUserRequest(Request[UserCreatedResponse]):
                def __init__(self, username: str):
                    self.username = username

            class CreateUserHandler(Handler[CreateUserRequest]):
                async def __call__(
                    self, request: CreateUserRequest
                ) -> UserCreatedResponse:
                    user_id = await async_generate_id()
                    return UserCreatedResponse(user_id=user_id)

            # Create async behaviors
            logging = AsyncLoggingBehavior()
            timing = AsyncTimingBehavior()

            # Build async pipeline
            handler = CreateUserHandler()
            pipeline = Pipeline([logging, timing], handler)

            # Execute request through pipeline
            request = CreateUserRequest(username="alice")
            response = await pipeline(request)
            ```

        Pipeline with database transactions:
            ```python
            async def create_user_pipeline(db: AsyncDatabase):
                handler = CreateUserHandler(db)
                return Pipeline(
                    behaviors=[
                        AsyncLoggingBehavior(),
                        TransactionBehavior(db),
                        ValidationBehavior(),
                    ],
                    handler=handler
                )

            pipeline = await create_user_pipeline(db)
            response = await pipeline(CreateUserRequest(username="alice"))
            ```

    Note:
        The behaviors list is evaluated left-to-right, so the first behavior
        in the list is the outermost wrapper (executes first).

        For synchronous pipelines, use `pymediate.pipeline.Pipeline` instead.

    See Also:
        - PipelineBehavior: Protocol for individual async behaviors
        - pymediate.pipeline.Pipeline: Sync version
    """

    def __init__(
        self,
        behaviors: Sequence[Any],
        handler: Handler[RequestT],
    ) -> None:
        """Initialize an async pipeline with behaviors and a handler.

        Args:
            behaviors: Sequence of async behaviors to execute in order (can be empty)
            handler: The final async handler that processes the request

        Note:
            Behaviors are executed in the order provided in the sequence.
            The first behavior in the sequence is the outermost wrapper.
        """
        self._behaviors = behaviors
        self._handler = handler

    async def __call__(self, request: RequestT) -> ResponseT:
        """Process a request asynchronously through the pipeline.

        Executes each async behavior in order, with each behavior wrapping the next,
        ultimately calling the async handler to produce the response.

        Args:
            request: The request to process

        Returns:
            The response from the handler, potentially modified by behaviors

        Examples:
            ```python
            pipeline = Pipeline([logging, timing], handler)
            response = await pipeline(CreateUserRequest(username="alice"))
            ```

        Note:
            If no behaviors are provided, this directly awaits the handler.
            Behaviors execute in the order they were provided to the constructor.
        """
        from typing import cast

        # Build the chain from the inside out (handler first, then behaviors)
        # Start with the handler as the innermost callable
        async def handler_call() -> ResponseT:
            result = await self._handler(request)
            return cast(ResponseT, result)

        # Wrap with behaviors in reverse order so they execute in the correct order
        next_call: Callable[[], Awaitable[ResponseT]] = handler_call

        for behavior in reversed(self._behaviors):
            # Capture the current next_call in the closure
            current_next = next_call

            def create_behavior_call(
                b: Any,
                n: Callable[[], Awaitable[ResponseT]],
            ) -> Callable[[], Awaitable[ResponseT]]:
                async def behavior_call() -> ResponseT:
                    return await b(request, n)  # type: ignore[no-any-return]

                return behavior_call

            next_call = create_behavior_call(behavior, current_next)

        # Execute the outermost behavior (or handler if no behaviors)
        return await next_call()


__all__ = [
    "PipelineBehavior",
    "Pipeline",
]
