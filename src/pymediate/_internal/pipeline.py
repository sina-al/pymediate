"""Behavior-chain composition used by the mediators (ADR 0003).

A chain is composed inside out: the handler is the innermost step, and each
behavior wraps the chain built so far. Composition happens once per dispatch
today; the composed callable itself adds only one closure per behavior.
"""

from collections.abc import Awaitable, Callable, Sequence
from typing import Any


def compose(behaviors: Sequence[Any], handler: Callable[[Any], Any]) -> Callable[[Any], Any]:
    """Compose behaviors around a sync handler into a single callable.

    Args:
        behaviors: Behaviors to execute in order; the first is the outermost wrapper.
        handler: The final callable that processes the request.

    Returns:
        A callable taking the request and returning the handler's response.
    """
    chain = handler
    for behavior in reversed(behaviors):
        chain = _wrap(behavior, chain)
    return chain


def _wrap(behavior: Any, next_step: Callable[[Any], Any]) -> Callable[[Any], Any]:
    def step(request: Any) -> Any:
        return behavior(request, lambda: next_step(request))

    return step


def compose_async(
    behaviors: Sequence[Any], handler: Callable[[Any], Awaitable[Any]]
) -> Callable[[Any], Awaitable[Any]]:
    """Compose behaviors around an async handler into a single awaitable callable.

    Args:
        behaviors: Async behaviors to execute in order; the first is the outermost wrapper.
        handler: The final async callable that processes the request.

    Returns:
        An async callable taking the request and returning the handler's response.
    """
    chain = handler
    for behavior in reversed(behaviors):
        chain = _wrap_async(behavior, chain)
    return chain


def _wrap_async(
    behavior: Any, next_step: Callable[[Any], Awaitable[Any]]
) -> Callable[[Any], Awaitable[Any]]:
    async def step(request: Any) -> Any:
        return await behavior(request, lambda: next_step(request))

    return step
