"""Sending a StreamRequest through send() instead of stream() - should fail mypy."""

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

# ERROR: send takes a Request; a StreamRequest is dispatched with stream()
mediator.send(Count(n=3))
