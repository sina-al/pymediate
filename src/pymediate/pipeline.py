"""Asynchronous request pipeline behaviors and their continuation type."""

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from typing import Any, ClassVar, TypeVar, get_args, get_origin

from .request import Request

type Next[ResponseT] = Callable[[], Awaitable[ResponseT]]
"""The continuation handed to a behavior's ``__call__``.

Awaiting it runs the rest of the pipeline - the remaining behaviors and, finally,
the handler - and yields the response. ``ResponseT`` is the response type the
behavior expects back; annotate it concretely (``Next[OrderReceipt]``) to keep the
call site typed, or ``Next[Any]`` for a universal behavior that passes the response
through untouched. ``pymediate.sync.Next`` is the synchronous
``Callable[[], ResponseT]`` variant.
"""


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

    A behavior can run logic before and after the next behavior or request handler.
    Awaiting ``next()`` continues the chain. Returning without awaiting it
    short-circuits dispatch, and the behavior's return value becomes the result of
    ``Mediator.send()``.

    The type parameter controls selection. ``PipelineBehavior[Request[Any]]``
    applies to every request; a concrete request class applies to that class and,
    by default, its subclasses. Set ``apply_to_subclasses`` to ``False`` for an
    exact-type match, or override ``should_apply()`` for other conditions.

    Type Parameters:
        RequestT: The ``Request`` subclass or request-class family this behavior wraps.

    Examples:
        Defining a behavior that applies to every request:
            ```python
            from typing import Any

            from pymediate import Next, PipelineBehavior, Request

            class LoggingBehavior(PipelineBehavior[Request[Any]]):
                async def __call__(
                    self,
                    request: Request[Any],
                    next: Next[Any],
                ) -> Any:
                    print(f"handling {type(request).__name__}")
                    response = await next()
                    print(f"handled {type(request).__name__}")
                    return response
            ```

    Attributes:
        apply_to_subclasses: Whether the default selector includes subclasses of
            ``RequestT``. Defaults to ``True``.

    Note:
        For a behavior scoped to one request type, annotate ``next`` and the
        return value with that request's concrete response type. Use ``Next[Any]``
        and return ``Any`` when the behavior can wrap several response types.
        Pipeline behaviors apply to ``send()`` only, not ``stream()`` or
        ``publish()``. Use ``pymediate.sync.PipelineBehavior`` for synchronous code.
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

        The default selector matches the behavior's request type. It uses
        ``isinstance()`` when ``apply_to_subclasses`` is true and an exact type
        comparison otherwise. Override this method for request-dependent selection.

        Args:
            request: The request to check.

        Returns:
            ``True`` when the behavior should join the request's pipeline.
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
        next: Next[Any],
    ) -> Any:
        """Execute the behavior's async logic and await next to continue the pipeline.

        Args:
            request: The request being processed.
            next: Async continuation that invokes the next behavior or handler in
                the chain.

        Returns:
            The response to return from ``Mediator.send()``.

        Note:
            Await ``next()`` to continue the chain. A behavior may instead return
            directly to short-circuit it.
        """
        ...


__all__ = [
    "Next",
    "PipelineBehavior",
]
