"""Behavior modifying the response - type safety should be maintained."""

from collections.abc import Callable
from dataclasses import dataclass

from pymediate import Handler, Mediator, PipelineBehavior, Request, Services


@dataclass
class ProcessedResponse:
    value: int
    processed: bool


@dataclass
class ProcessRequest(Request[ProcessedResponse]):
    data: str


class ProcessHandler(Handler[ProcessRequest]):
    def __call__(self, request: ProcessRequest) -> ProcessedResponse:
        return ProcessedResponse(value=42, processed=False)


class ProcessingBehavior(PipelineBehavior[ProcessRequest]):
    """Behavior that modifies the response."""

    def __call__(
        self,
        request: ProcessRequest,
        next: Callable[[], ProcessedResponse],
    ) -> ProcessedResponse:
        response = next()
        # Modify response
        response.processed = True
        response.value *= 2
        return response


services = Services()
services.add(ProcessingBehavior())
services.add(ProcessHandler())
mediator = Mediator(services.provider())

response = mediator.send(ProcessRequest(data="test"))

# Mypy should know the response type and allow these accesses
value: int = response.value
processed: bool = response.processed

# These should be valid operations on the correct types
if response.processed:
    result: int = response.value + 10
