"""The pymediate / pymediate.sync mirror contract (ADR 0008, issue #45).

The top-level package is the async API; `pymediate.sync` is its structural
mirror. These tests pin the contract so future top-level additions can't
drift: every public name exists on both sides, shared names are the identical
object, and only the four intentional variants differ.
"""

import inspect
from collections.abc import AsyncIterator, Iterator
from typing import get_origin, get_type_hints

import pytest

import pymediate
import pymediate.sync

# The only names allowed to differ between the two namespaces: each side has
# its own handler/mediator/behavior classes. Everything else is shared.
INTENTIONAL_VARIANTS = frozenset(
    {
        "RequestHandler",
        "EventHandler",
        "StreamRequestHandler",
        "Mediator",
        "PipelineBehavior",
    }
)


def test_sync_all_mirrors_top_level_all() -> None:
    """Every top-level public name appears in pymediate.sync.__all__ (superset rule)."""
    missing = set(pymediate.__all__) - set(pymediate.sync.__all__)
    assert not missing, f"pymediate.sync.__all__ is missing: {sorted(missing)}"


def test_shared_names_are_the_identical_objects() -> None:
    """Shared names are one definition re-exported, never a parallel copy."""
    for name in set(pymediate.__all__) - INTENTIONAL_VARIANTS:
        assert getattr(pymediate, name) is getattr(pymediate.sync, name), (
            f"pymediate.{name} and pymediate.sync.{name} must be the same object"
        )


def test_variant_names_are_distinct_objects() -> None:
    """The intentional variants really are different classes on each side."""
    for name in INTENTIONAL_VARIANTS:
        assert getattr(pymediate, name) is not getattr(pymediate.sync, name), (
            f"pymediate.{name} and pymediate.sync.{name} must be distinct variants"
        )


def test_variants_split_async_and_sync() -> None:
    """Top-level variants are the async side; pymediate.sync variants are sync."""
    for name in ("RequestHandler", "EventHandler", "PipelineBehavior"):
        assert inspect.iscoroutinefunction(getattr(pymediate, name).__call__)
        assert not inspect.iscoroutinefunction(getattr(pymediate.sync, name).__call__)
    for method in ("send", "publish"):
        assert inspect.iscoroutinefunction(getattr(pymediate.Mediator, method))
        assert not inspect.iscoroutinefunction(getattr(pymediate.sync.Mediator, method))


def test_stream_variants_split_async_and_sync() -> None:
    """Stream handlers/method split by iterator kind, not coroutine-ness.

    A stream handler's __call__ is a generator (async-gen on the async side, plain
    generator on the sync side), and Mediator.stream returns the iterator directly -
    neither is a coroutine function, so the split shows up in the return annotation.
    """
    async_call_return = get_type_hints(pymediate.StreamRequestHandler.__call__)["return"]
    sync_call_return = get_type_hints(pymediate.sync.StreamRequestHandler.__call__)["return"]
    assert get_origin(async_call_return) is AsyncIterator
    assert get_origin(sync_call_return) is Iterator

    async_stream_return = get_type_hints(pymediate.Mediator.stream)["return"]
    sync_stream_return = get_type_hints(pymediate.sync.Mediator.stream)["return"]
    assert get_origin(async_stream_return) is AsyncIterator
    assert get_origin(sync_stream_return) is Iterator


def test_aio_namespace_is_gone() -> None:
    """The 0.4.x async namespace is removed outright - no alias, no shim."""
    with pytest.raises(ModuleNotFoundError):
        import pymediate.aio  # noqa: F401
