"""Asynchronous pipeline behavior implementation for cross-cutting concerns.

This module provides async/await compatible pipeline behaviors for the mediator pattern.
All behaviors and the pipeline itself are fully asynchronous, allowing for async operations
in the middleware chain.

See Also:
    - pymediate.pipeline: Synchronous pipeline implementation
"""

from collections.abc import Awaitable, Callable, Sequence
from typing import Protocol

from .handler import Handler


class PipelineBehavior[RequestT, ResponseT](Protocol):
    """Protocol for asynchronous pipeline behaviors that wrap request processing.

    An async pipeline behavior is middleware that sits between the mediator and the
    handler, allowing you to execute asynchronous logic before and after the handler
    processes the request.

    Behaviors receive:
    - The request being processed
    - A 'next' callable that represents the next step in the pipeline (either the
      next behavior or the final handler)

    By awaiting next(), the behavior passes control to the next step. The behavior
    can execute code before awaiting next() (pre-processing), after awaiting next()
    (post-processing), or both.

    Type Parameters:
        RequestT: The request type this behavior handles (must extend Request)
        ResponseT: The response type returned by the handler

    Examples:
        Async logging behavior:
            ```python
            from pymediate import Request
            from pymediate.aio.pipeline import PipelineBehavior

            class AsyncLoggingBehavior[RequestT: Request, ResponseT]:
                async def __call__(
                    self,
                    request: RequestT,
                    next: Callable[[], Awaitable[ResponseT]]
                ) -> ResponseT:
                    await log_to_database(f"Handling: {type(request).__name__}")
                    response = await next()
                    await log_to_database(f"Handled: {type(request).__name__}")
                    return response
            ```

        Async caching behavior:
            ```python
            class CachingBehavior[RequestT: Request, ResponseT]:
                def __init__(self, cache: AsyncCache):
                    self.cache = cache

                async def __call__(
                    self,
                    request: RequestT,
                    next: Callable[[], Awaitable[ResponseT]]
                ) -> ResponseT:
                    cache_key = f"{type(request).__name__}:{hash(request)}"

                    # Check cache
                    cached = await self.cache.get(cache_key)
                    if cached is not None:
                        return cached

                    # Execute and cache
                    response = await next()
                    await self.cache.set(cache_key, response)
                    return response
            ```

        Database transaction behavior:
            ```python
            class TransactionBehavior[RequestT: Request, ResponseT]:
                def __init__(self, db: AsyncDatabase):
                    self.db = db

                async def __call__(
                    self,
                    request: RequestT,
                    next: Callable[[], Awaitable[ResponseT]]
                ) -> ResponseT:
                    async with self.db.transaction():
                        return await next()
            ```

    Note:
        The behavior must await next() to continue the pipeline. If next() is not
        awaited, the request will not be processed by subsequent behaviors or the
        handler.

        For synchronous behaviors, use `pymediate.pipeline.PipelineBehavior` instead.

    See Also:
        - Pipeline: Chains multiple async behaviors together
        - pymediate.pipeline.PipelineBehavior: Sync version
    """

    async def __call__(
        self,
        request: RequestT,
        next: Callable[[], Awaitable[ResponseT]],
    ) -> ResponseT:
        """Execute the behavior's async logic and await next to continue the pipeline.

        Args:
            request: The request being processed
            next: Async callable that invokes the next behavior or handler in the chain

        Returns:
            The response from the handler (potentially modified by this behavior)

        Note:
            This method should await next() to continue the pipeline execution.
            Code before next() runs before the handler, code after runs after.
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
        behaviors: Sequence[PipelineBehavior[RequestT, ResponseT]],
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
                b: PipelineBehavior[RequestT, ResponseT],
                n: Callable[[], Awaitable[ResponseT]],
            ) -> Callable[[], Awaitable[ResponseT]]:
                async def behavior_call() -> ResponseT:
                    return await b(request, n)

                return behavior_call

            next_call = create_behavior_call(behavior, current_next)

        # Execute the outermost behavior (or handler if no behaviors)
        return await next_call()


__all__ = [
    "PipelineBehavior",
    "Pipeline",
]
