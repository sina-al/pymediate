"""Assigning a stream chunk to the wrong element type - should fail mypy."""

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

for value in mediator.stream(Count(n=3)):
    # ERROR: stream() yields int (from StreamRequest[int]), not str
    chunk: str = value
    print(chunk)
