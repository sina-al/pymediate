"""Tests for the streaming example — the examples contract's `uv run pytest` entrypoint."""

import pytest
from pymediate import HandlerNotFoundError, Mediator

from app import COMPLETION, StreamAudioClip, StreamCompletion, build_mediator


@pytest.fixture
def emitted() -> list[str]:
    return []


@pytest.fixture
def mediator(emitted: list[str]) -> Mediator:
    return build_mediator(emitted)


async def test_streams_the_exact_token_sequence(mediator: Mediator) -> None:
    tokens = [token async for token in mediator.stream(StreamCompletion(prompt="hi"))]

    assert tokens == list(COMPLETION)


async def test_each_chunk_is_typed_str(mediator: Mediator) -> None:
    async for token in mediator.stream(StreamCompletion(prompt="hi")):
        assert isinstance(token, str)


async def test_production_interleaves_with_consumption(
    mediator: Mediator, emitted: list[str]
) -> None:
    # The model records each token as it emits it. If iteration is lazy, the emitted count
    # never runs ahead of what we've consumed — it grows one token at a time.
    consumed = 0
    async for _token in mediator.stream(StreamCompletion(prompt="hi")):
        consumed += 1
        assert len(emitted) == consumed


async def test_early_break_stops_production(mediator: Mediator, emitted: list[str]) -> None:
    received: list[str] = []
    async for token in mediator.stream(StreamCompletion(prompt="hi")):
        received.append(token)
        if len(received) == 3:
            break

    assert received == list(COMPLETION[:3])
    # Tokens after the break were never generated — laziness, proven.
    assert emitted == list(COMPLETION[:3])


async def test_unregistered_stream_resolves_eagerly(mediator: Mediator, emitted: list[str]) -> None:
    # No handler is registered for StreamAudioClip, so stream() raises at the call itself,
    # before any chunk is pulled — resolution is eager even though iteration is lazy.
    with pytest.raises(HandlerNotFoundError):
        mediator.stream(StreamAudioClip(clip_id="clip-1"))

    assert emitted == []
