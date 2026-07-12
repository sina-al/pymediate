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
from collections.abc import Callable
from typing import Any, ClassVar, TypeVar, get_args, get_origin

from ..request import Request


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
            from pymediate.sync import PipelineBehavior, Request

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

        For async behaviors, use `pymediate.PipelineBehavior` instead.

    See Also:
        - Mediator.send: Discovers applicable behaviors and runs them
          around the handler.
        - should_apply: Override to customize behavior selection logic
        - pymediate.PipelineBehavior: Async version
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
        match_type = cls.__match_type__
        if match_type is Request:
            return True  # Universal behavior

        if cls.apply_to_subclasses:
            return isinstance(request, match_type)
        return type(request) is match_type

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


__all__ = [
    "PipelineBehavior",
]
