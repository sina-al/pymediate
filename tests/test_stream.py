"""Tests for StreamRequest, the sync/async StreamRequestHandler, and Mediator.stream."""

from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass

import pytest

import pymediate
import pymediate.sync
from pymediate import (
    HandlerAlreadyRegisteredError,
    HandlerNotFoundError,
    InvalidHandlerSignatureError,
    InvalidStreamRequestTypeError,
)
from pymediate._internal import registry


def test_stream_request_registers_chunk_type() -> None:
    """A StreamRequest subclass records its chunk type in the registry."""

    @dataclass
    class StreamCompletion(pymediate.StreamRequest[str]):
        prompt: str

    assert registry.get_response_type(StreamCompletion) is str


def test_stream_handler_extracts_request_and_chunk_type() -> None:
    """A stream handler records its stream request type and inferred chunk type."""

    @dataclass
    class StreamCompletion(pymediate.StreamRequest[str]):
        prompt: str

    class CompletionHandler(pymediate.StreamRequestHandler[StreamCompletion]):
        async def __call__(self, request: StreamCompletion) -> AsyncIterator[str]:
            yield request.prompt

    assert CompletionHandler.get_stream_request_type() is StreamCompletion
    assert CompletionHandler.get_chunk_type() is str


def test_stream_handler_is_registered() -> None:
    """A stream handler registers in the one-handler-per-request registry."""

    @dataclass
    class Export(pymediate.StreamRequest[int]):
        n: int

    class ExportHandler(pymediate.StreamRequestHandler[Export]):
        async def __call__(self, request: Export) -> AsyncIterator[int]:
            for i in range(request.n):
                yield i

    assert registry.has_handler(Export)
    assert registry.get_handler_class(Export) is ExportHandler


def test_second_stream_handler_for_same_request_is_rejected() -> None:
    """One stream handler per stream request type, same as request handlers."""

    @dataclass
    class Export(pymediate.StreamRequest[int]):
        n: int

    class First(pymediate.StreamRequestHandler[Export]):
        async def __call__(self, request: Export) -> AsyncIterator[int]:
            yield 1

    with pytest.raises(HandlerAlreadyRegisteredError):

        class Second(pymediate.StreamRequestHandler[Export]):
            async def __call__(self, request: Export) -> AsyncIterator[int]:
                yield 2


# --------------------------------------------------------------------------- #
# Sync dispatch
# --------------------------------------------------------------------------- #


def test_sync_stream_yields_typed_chunks() -> None:
    """Sync Mediator.stream returns the handler's generator, iterated lazily."""

    @dataclass
    class Count(pymediate.sync.StreamRequest[int]):
        n: int

    class CountHandler(pymediate.sync.StreamRequestHandler[Count]):
        def __call__(self, request: Count) -> Iterator[int]:
            yield from range(request.n)

    mediator = pymediate.sync.Mediator(pymediate.sync.Services().add(CountHandler()).provider())

    assert list(mediator.stream(Count(n=3))) == [0, 1, 2]


def test_sync_stream_is_lazy() -> None:
    """The handler body runs only as chunks are pulled."""

    @dataclass
    class Count(pymediate.sync.StreamRequest[int]):
        n: int

    produced: list[int] = []

    class CountHandler(pymediate.sync.StreamRequestHandler[Count]):
        def __call__(self, request: Count) -> Iterator[int]:
            for i in range(request.n):
                produced.append(i)
                yield i

    mediator = pymediate.sync.Mediator(pymediate.sync.Services().add(CountHandler()).provider())

    stream = mediator.stream(Count(n=3))
    assert produced == []  # Nothing produced until iteration starts.
    assert next(stream) == 0
    assert produced == [0]
    assert list(stream) == [1, 2]
    assert produced == [0, 1, 2]


def test_sync_stream_missing_handler_raises_eagerly() -> None:
    """A missing handler raises at the stream() call, not on first iteration."""

    @dataclass
    class Unhandled(pymediate.sync.StreamRequest[int]):
        pass

    mediator = pymediate.sync.Mediator(pymediate.sync.Services().provider())

    with pytest.raises(HandlerNotFoundError):
        mediator.stream(Unhandled())


# --------------------------------------------------------------------------- #
# Async dispatch
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_async_stream_yields_typed_chunks() -> None:
    """Async Mediator.stream returns the handler's async generator."""

    @dataclass
    class StreamCompletion(pymediate.StreamRequest[str]):
        prompt: str

    class CompletionHandler(pymediate.StreamRequestHandler[StreamCompletion]):
        async def __call__(self, request: StreamCompletion) -> AsyncIterator[str]:
            for token in request.prompt.split():
                yield token

    mediator = pymediate.Mediator(pymediate.Services().add(CompletionHandler()).provider())

    chunks = [tok async for tok in mediator.stream(StreamCompletion(prompt="a b c"))]
    assert chunks == ["a", "b", "c"]


@pytest.mark.asyncio
async def test_async_stream_is_lazy() -> None:
    """The async handler body runs only as chunks are pulled."""

    @dataclass
    class Count(pymediate.StreamRequest[int]):
        n: int

    produced: list[int] = []

    class CountHandler(pymediate.StreamRequestHandler[Count]):
        async def __call__(self, request: Count) -> AsyncIterator[int]:
            for i in range(request.n):
                produced.append(i)
                yield i

    mediator = pymediate.Mediator(pymediate.Services().add(CountHandler()).provider())

    stream = mediator.stream(Count(n=3))
    assert produced == []  # Nothing produced until iteration starts.
    assert await anext(stream) == 0
    assert produced == [0]


def test_async_stream_missing_handler_raises_eagerly() -> None:
    """A missing handler raises at the stream() call, before any iteration."""

    @dataclass
    class Unhandled(pymediate.StreamRequest[int]):
        pass

    mediator = pymediate.Mediator(pymediate.Services().provider())

    # No await/iteration - resolution happens synchronously in stream().
    with pytest.raises(HandlerNotFoundError):
        mediator.stream(Unhandled())


# --------------------------------------------------------------------------- #
# Definition-time validation
# --------------------------------------------------------------------------- #


def test_non_stream_request_type_argument_is_rejected() -> None:
    """StreamRequestHandler's type parameter must inherit from StreamRequest."""

    @dataclass
    class NotAStream:
        pass

    with pytest.raises(InvalidStreamRequestTypeError):

        class BadHandler(pymediate.StreamRequestHandler[NotAStream]):  # type: ignore[type-var]
            async def __call__(self, request: NotAStream) -> AsyncIterator[str]:
                yield "x"


def test_async_handler_must_be_async_generator() -> None:
    """A plain async def that returns an iterator (no yield) is rejected."""

    @dataclass
    class S(pymediate.StreamRequest[str]):
        pass

    with pytest.raises(InvalidHandlerSignatureError, match="async generator"):

        class BadHandler(pymediate.StreamRequestHandler[S]):
            async def __call__(self, request: S) -> AsyncIterator[str]:
                return iter([])  # type: ignore[return-value]  # no yield -> coroutine


def test_sync_handler_must_be_generator() -> None:
    """A plain def that returns an iterator (no yield) is rejected."""

    @dataclass
    class S(pymediate.sync.StreamRequest[str]):
        pass

    with pytest.raises(InvalidHandlerSignatureError, match="must be a generator"):

        class BadHandler(pymediate.sync.StreamRequestHandler[S]):
            def __call__(self, request: S) -> Iterator[str]:
                return iter([])  # no yield


def test_sync_handler_rejects_async_generator() -> None:
    """A sync stream handler whose __call__ is an async generator is rejected."""

    @dataclass
    class S(pymediate.sync.StreamRequest[str]):
        pass

    with pytest.raises(InvalidHandlerSignatureError, match="must be a generator"):

        class BadHandler(pymediate.sync.StreamRequestHandler[S]):
            async def __call__(self, request: S) -> AsyncIterator[str]:
                yield "x"


def test_return_annotation_must_be_iterator_of_chunk_type() -> None:
    """The return annotation must be AsyncIterator[ChunkT], not the element type."""

    @dataclass
    class S(pymediate.StreamRequest[str]):
        pass

    with pytest.raises(InvalidHandlerSignatureError, match="AsyncIterator"):

        class BadHandler(pymediate.StreamRequestHandler[S]):
            async def __call__(self, request: S) -> str:
                yield "x"


def test_return_annotation_chunk_type_must_match() -> None:
    """The iterator's element type must match the request's declared chunk type."""

    @dataclass
    class S(pymediate.StreamRequest[str]):
        pass

    with pytest.raises(InvalidHandlerSignatureError, match=r"AsyncIterator\[str\]"):

        class BadHandler(pymediate.StreamRequestHandler[S]):
            async def __call__(self, request: S) -> AsyncIterator[int]:
                yield 1


def test_request_parameter_must_be_exact_type() -> None:
    """A base-class request annotation is rejected (ADR 0004 exact-annotation contract)."""

    @dataclass
    class Base(pymediate.StreamRequest[str]):
        pass

    @dataclass
    class Derived(Base):
        pass

    with pytest.raises(InvalidHandlerSignatureError, match="exact"):

        class BadHandler(pymediate.StreamRequestHandler[Derived]):
            async def __call__(self, request: Base) -> AsyncIterator[str]:
                yield "x"


def test_stream_request_without_chunk_type_is_rejected() -> None:
    """A StreamRequest subclass with no declared chunk type can't be handled."""

    class Bare(pymediate.StreamRequest):  # type: ignore[type-arg]  # no [ChunkT]
        pass

    with pytest.raises(InvalidStreamRequestTypeError):

        class BadHandler(pymediate.StreamRequestHandler[Bare]):
            async def __call__(self, request: Bare) -> AsyncIterator[str]:
                yield "x"
