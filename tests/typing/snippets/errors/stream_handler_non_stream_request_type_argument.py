"""Parameterizing StreamRequestHandler with a non-StreamRequest type - should fail mypy."""

from collections.abc import Iterator
from dataclasses import dataclass
from typing import override

from pymediate.sync import StreamRequestHandler


@dataclass
class NotAStreamRequest:
    prompt: str


# ERROR: StreamRequestHandler's type parameter is bound to StreamRequest
class CompletionHandler(StreamRequestHandler[NotAStreamRequest]):
    @override
    def __call__(self, request: NotAStreamRequest) -> Iterator[str]:
        yield request.prompt
