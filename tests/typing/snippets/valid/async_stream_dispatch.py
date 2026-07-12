"""Async streaming dispatch with typed chunks - should pass mypy."""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import override

from pymediate import Mediator, Services, StreamRequest, StreamRequestHandler


@dataclass
class StreamCompletion(StreamRequest[str]):
    prompt: str


class CompletionHandler(StreamRequestHandler[StreamCompletion]):
    @override
    async def __call__(self, request: StreamCompletion) -> AsyncIterator[str]:
        for token in request.prompt.split():
            yield token


async def main() -> None:
    provider = Services().add(CompletionHandler()).provider()
    mediator = Mediator(provider)

    collected: list[str] = []
    # stream() infers the element type as str from StreamRequest[str].
    async for token in mediator.stream(StreamCompletion(prompt="hello typed world")):
        chunk: str = token  # Mypy should infer token as str
        collected.append(chunk)

    assert collected == ["hello", "typed", "world"]
