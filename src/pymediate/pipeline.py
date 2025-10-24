"""Pipeline behavior implementation for cross-cutting concerns in the mediator pattern.

Pipeline behaviors provide a way to implement middleware-like functionality that wraps
around request handlers. This is inspired by MediatR's IPipelineBehavior pattern and
enables clean implementation of cross-cutting concerns such as:

- Logging and auditing
- Performance measurement and monitoring
- Validation
- Transaction management
- Caching
- Error handling and retry logic

Behaviors are executed in the order they are registered, forming a chain where each
behavior can execute logic before and after the next behavior (or final handler) runs.
"""

from collections.abc import Callable, Sequence
from typing import Protocol

from .handler import Handler


class PipelineBehavior[RequestT, ResponseT](Protocol):
    """Protocol for pipeline behaviors that wrap request processing.

    A pipeline behavior is middleware that sits between the mediator and the handler,
    allowing you to execute logic before and after the handler processes the request.

    Behaviors receive:
    - The request being processed
    - A 'next' callable that represents the next step in the pipeline (either the
      next behavior or the final handler)

    By calling next(), the behavior passes control to the next step. The behavior
    can execute code before calling next() (pre-processing), after calling next()
    (post-processing), or both.

    Type Parameters:
        RequestT: The request type this behavior handles (must extend Request)
        ResponseT: The response type returned by the handler

    Examples:
        Simple logging behavior:
            ```python
            from pymediate import Request
            from pymediate.pipeline import PipelineBehavior

            class LoggingBehavior[RequestT: Request, ResponseT]:
                def __call__(
                    self,
                    request: RequestT,
                    next: Callable[[], ResponseT]
                ) -> ResponseT:
                    print(f"Handling: {type(request).__name__}")
                    response = next()
                    print(f"Handled: {type(request).__name__}")
                    return response
            ```

        Timing behavior:
            ```python
            import time

            class TimingBehavior[RequestT: Request, ResponseT]:
                def __call__(
                    self,
                    request: RequestT,
                    next: Callable[[], ResponseT]
                ) -> ResponseT:
                    start = time.time()
                    response = next()
                    duration = time.time() - start
                    print(f"Request handled in {duration:.4f}s")
                    return response
            ```

        Validation behavior:
            ```python
            class ValidationBehavior[RequestT: Request, ResponseT]:
                def __call__(
                    self,
                    request: RequestT,
                    next: Callable[[], ResponseT]
                ) -> ResponseT:
                    # Validate request before processing
                    if hasattr(request, 'validate'):
                        request.validate()
                    return next()
            ```

    Note:
        The behavior must call next() to continue the pipeline. If next() is not
        called, the request will not be processed by subsequent behaviors or the
        handler.

        For async behaviors, use `pymediate.aio.pipeline.PipelineBehavior` instead.

    See Also:
        - Pipeline: Chains multiple behaviors together
        - pymediate.aio.pipeline.PipelineBehavior: Async version
    """

    def __call__(
        self,
        request: RequestT,
        next: Callable[[], ResponseT],
    ) -> ResponseT:
        """Execute the behavior's logic and call next to continue the pipeline.

        Args:
            request: The request being processed
            next: Callable that invokes the next behavior or handler in the chain

        Returns:
            The response from the handler (potentially modified by this behavior)

        Note:
            This method should call next() to continue the pipeline execution.
            Code before next() runs before the handler, code after runs after.
        """
        ...


class Pipeline[RequestT, ResponseT]:
    """Chains multiple pipeline behaviors together to form a request processing pipeline.

    The Pipeline class combines multiple behaviors and a handler into a single callable
    that processes requests through the behavior chain before reaching the final handler.

    Behaviors are executed in the order provided, with each behavior wrapping the next
    one, ultimately wrapping the final handler.

    Type Parameters:
        RequestT: The request type (must extend Request)
        ResponseT: The response type returned by the handler

    Attributes:
        _behaviors: Sequence of behaviors to execute in order
        _handler: The final handler that processes the request

    Examples:
        Basic pipeline with logging and timing:
            ```python
            from pymediate import Handler, Request
            from pymediate.pipeline import Pipeline

            class UserCreatedResponse:
                def __init__(self, user_id: int):
                    self.user_id = user_id

            class CreateUserRequest(Request[UserCreatedResponse]):
                def __init__(self, username: str):
                    self.username = username

            class CreateUserHandler(Handler[CreateUserRequest]):
                def __call__(self, request: CreateUserRequest) -> UserCreatedResponse:
                    return UserCreatedResponse(user_id=1)

            # Create behaviors
            logging = LoggingBehavior()
            timing = TimingBehavior()

            # Build pipeline
            handler = CreateUserHandler()
            pipeline = Pipeline([logging, timing], handler)

            # Execute request through pipeline
            request = CreateUserRequest(username="alice")
            response = pipeline(request)
            # Output:
            # Handling: CreateUserRequest
            # Request handled in 0.0001s
            # Handled: CreateUserRequest
            ```

        Pipeline without behaviors (just handler):
            ```python
            # Pipeline with no behaviors is equivalent to calling handler directly
            pipeline = Pipeline([], handler)
            response = pipeline(request)
            ```

        Reusable pipeline factory:
            ```python
            def create_pipeline[Req: Request, Resp](
                handler: Handler[Req]
            ) -> Pipeline[Req, Resp]:
                return Pipeline(
                    behaviors=[
                        LoggingBehavior(),
                        ValidationBehavior(),
                        TimingBehavior(),
                    ],
                    handler=handler
                )
            ```

    Note:
        The behaviors list is evaluated left-to-right, so the first behavior
        in the list is the outermost wrapper (executes first).

        For async pipelines, use `pymediate.aio.pipeline.Pipeline` instead.

    See Also:
        - PipelineBehavior: Protocol for individual behaviors
        - pymediate.aio.pipeline.Pipeline: Async version
    """

    def __init__(
        self,
        behaviors: Sequence[PipelineBehavior[RequestT, ResponseT]],
        handler: Handler[RequestT],
    ) -> None:
        """Initialize a pipeline with behaviors and a handler.

        Args:
            behaviors: Sequence of behaviors to execute in order (can be empty)
            handler: The final handler that processes the request

        Note:
            Behaviors are executed in the order provided in the sequence.
            The first behavior in the sequence is the outermost wrapper.
        """
        self._behaviors = behaviors
        self._handler = handler

    def __call__(self, request: RequestT) -> ResponseT:
        """Process a request through the pipeline.

        Executes each behavior in order, with each behavior wrapping the next,
        ultimately calling the handler to produce the response.

        Args:
            request: The request to process

        Returns:
            The response from the handler, potentially modified by behaviors

        Examples:
            ```python
            pipeline = Pipeline([logging, timing], handler)
            response = pipeline(CreateUserRequest(username="alice"))
            ```

        Note:
            If no behaviors are provided, this directly calls the handler.
            Behaviors execute in the order they were provided to the constructor.
        """
        from typing import cast

        # Build the chain from the inside out (handler first, then behaviors)
        # Start with the handler as the innermost callable
        def handler_call() -> ResponseT:
            return cast(ResponseT, self._handler(request))

        # Wrap with behaviors in reverse order so they execute in the correct order
        next_call: Callable[[], ResponseT] = handler_call

        for behavior in reversed(self._behaviors):
            # Capture the current next_call in the closure
            current_next = next_call

            def create_behavior_call(
                b: PipelineBehavior[RequestT, ResponseT],
                n: Callable[[], ResponseT],
            ) -> Callable[[], ResponseT]:
                def behavior_call() -> ResponseT:
                    return b(request, n)

                return behavior_call

            next_call = create_behavior_call(behavior, current_next)

        # Execute the outermost behavior (or handler if no behaviors)
        return next_call()


__all__ = [
    "PipelineBehavior",
    "Pipeline",
]
