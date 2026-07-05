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

from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from typing import Any, get_args, get_origin

from .handler import Handler
from .request import Request


class PipelineBehavior[RequestT: Request[Any]](ABC):
    """Abstract base class for pipeline behaviors that wrap request processing.

    A pipeline behavior is middleware that sits between the mediator and the handler,
    allowing you to execute logic before and after the handler processes the request.

    Behaviors can be selective - they only apply to specific request types or mixins.
    The type parameter indicates which requests this behavior applies to.

    Behaviors receive:
    - The request being processed (typed as RequestT)
    - A 'next' callable that represents the next step in the pipeline

    By calling next(), the behavior passes control to the next step. The behavior
    can execute code before calling next() (pre-processing), after calling next()
    (post-processing), or both.

    Type Parameters:
        RequestT: The request type (or mixin) this behavior applies to.
                  Can be Request (universal), a specific request class, or a mixin.

    Examples:
        Universal behavior (applies to all requests):
            ```python
            from pymediate import Request
            from pymediate.pipeline import PipelineBehavior

            class LoggingBehavior(PipelineBehavior[Request]):
                def __call__(
                    self,
                    request: Request,
                    next: Callable[[], Any]
                ) -> Any:
                    print(f"Handling: {type(request).__name__}")
                    response = next()
                    print(f"Handled: {type(request).__name__}")
                    return response
            ```

        Selective behavior for authenticated requests:
            ```python
            class AuthMixin:
                principal: Principal

            class AuthBehavior(PipelineBehavior[AuthMixin]):
                def __call__(
                    self,
                    request: AuthMixin,
                    next: Callable[[], Any]
                ) -> Any:
                    if not request.principal.is_authenticated:
                        raise Unauthorized()
                    return next()
            ```

        Specific request type:
            ```python
            class ValidationBehavior(PipelineBehavior[CreateUserRequest]):
                def __call__(
                    self,
                    request: CreateUserRequest,
                    next: Callable[[], Any]
                ) -> Any:
                    if not request.username:
                        raise ValueError("Username required")
                    return next()
            ```

    Attributes:
        apply_to_subclasses: If True (default), applies to subclasses of RequestT.
                            If False, only applies to exact type match.

    Note:
        The response type is not statically known because selective behaviors can
        apply to requests with different response types. If you need response type
        safety, manually annotate in your implementation:

            ```python
            def __call__(self, request: MyRequest, next) -> MyResponse:
                result: MyResponse = next()  # Manual type assertion
                return result
            ```

        For async behaviors, use `pymediate.aio.pipeline.PipelineBehavior` instead.

    See Also:
        - Pipeline: Chains multiple behaviors together
        - should_apply: Override to customize behavior selection logic
        - pymediate.aio.pipeline.PipelineBehavior: Async version
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
                class BusinessHoursBehavior(PipelineBehavior[Request]):
                    @classmethod
                    def should_apply(cls, request: Request) -> bool:
                        from datetime import datetime
                        return 9 <= datetime.now().hour < 17
                ```

            Multiple type matching:
                ```python
                class MultiTypeBehavior(PipelineBehavior[Request]):
                    @classmethod
                    def should_apply(cls, request: Request) -> bool:
                        return isinstance(request, (CreateRequest, UpdateRequest))
                ```
        """
        request_type = cls.__get_request_type__()
        if request_type is Request:
            return True  # Universal behavior

        # A subscripted generic like Request[Any] has no isinstance()/type() meaning of
        # its own - match against its origin (Request) instead.
        origin = get_origin(request_type)
        if origin is not None:
            request_type = origin

        if cls.apply_to_subclasses:
            return isinstance(request, request_type)
        return type(request) is request_type

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
    def __call__(
        self,
        request: RequestT,
        next: Callable[[], Any],
    ) -> Any:
        """Execute the behavior's logic and call next to continue the pipeline.

        Args:
            request: The request being processed (typed as RequestT)
            next: Callable that invokes the next behavior or handler in the chain

        Returns:
            The response from the handler (type not statically known)

        Note:
            This method should call next() to continue the pipeline execution.
            Code before next() runs before the handler, code after runs after.

            The response type is Any because selective behaviors can apply to
            requests with different response types. If you need type safety,
            manually annotate the return type in your implementation.
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

            class LoggingBehavior:
                def __call__(self, request, next):
                    print(f"Handling: {type(request).__name__}")
                    response = next()
                    print(f"Handled: {type(request).__name__}")
                    return response

            handler = CreateUserHandler()
            pipeline = Pipeline([LoggingBehavior()], handler)

            response = pipeline(CreateUserRequest(username="alice"))
            # Output:
            # Handling: CreateUserRequest
            # Handled: CreateUserRequest
            ```

        Pipeline without behaviors (equivalent to calling the handler directly):
            ```python
            pipeline = Pipeline([], handler)
            response = pipeline(request)
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
        behaviors: Sequence[Any],
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
                b: Any,
                n: Callable[[], ResponseT],
            ) -> Callable[[], ResponseT]:
                def behavior_call() -> ResponseT:
                    return b(request, n)  # type: ignore[no-any-return]

                return behavior_call

            next_call = create_behavior_call(behavior, current_next)

        # Execute the outermost behavior (or handler if no behaviors)
        return next_call()


__all__ = [
    "PipelineBehavior",
    "Pipeline",
]
