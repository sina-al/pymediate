"""Sync streaming dispatch with typed chunks - should pass mypy."""

from collections.abc import Iterator
from dataclasses import dataclass
from typing import override

from pymediate.sync import Mediator, Services, StreamRequest, StreamRequestHandler


@dataclass
class Count(StreamRequest[int]):
    n: int


class CountHandler(StreamRequestHandler[Count]):
    @override
    def __call__(self, request: Count) -> Iterator[int]:
        yield from range(request.n)


provider = Services().add(CountHandler()).provider()
mediator = Mediator(provider)

collected: list[int] = []
# stream() infers the element type as int from StreamRequest[int].
for value in mediator.stream(Count(n=3)):
    chunk: int = value  # Mypy should infer value as int
    collected.append(chunk)

assert collected == [0, 1, 2]
