"""Behavior modifying the response - type safety should be maintained."""

from dataclasses import dataclass
from typing import override

from pymediate.sync import Mediator, Next, PipelineBehavior, Request, RequestHandler, Services


@dataclass
class ProcessedResponse:
    value: int
    processed: bool


@dataclass
class ProcessRequest(Request[ProcessedResponse]):
    data: str


class ProcessHandler(RequestHandler[ProcessRequest]):
    @override
    def __call__(self, request: ProcessRequest) -> ProcessedResponse:
        return ProcessedResponse(value=42, processed=False)


class ProcessingBehavior(PipelineBehavior[ProcessRequest]):
    """Behavior that modifies the response."""

    @override
    def __call__(
        self,
        request: ProcessRequest,
        next: Next[ProcessedResponse],
    ) -> ProcessedResponse:
        response = next()
        # Modify response
        response.processed = True
        response.value *= 2
        return response


provider = Services().add(ProcessingBehavior()).add(ProcessHandler()).provider()
mediator = Mediator(provider)

response = mediator.send(ProcessRequest(data="test"))

# Mypy should know the response type and allow these accesses
value: int = response.value
processed: bool = response.processed

# These should be valid operations on the correct types
if response.processed:
    result: int = response.value + 10
