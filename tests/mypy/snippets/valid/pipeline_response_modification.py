"""Pipeline behavior modifying response - type safety should be maintained."""

from collections.abc import Callable
from dataclasses import dataclass

from pymediate import Handler, Request
from pymediate.pipeline import Pipeline


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


class ProcessingBehavior:
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


handler = ProcessHandler()
behavior = ProcessingBehavior()
pipeline = Pipeline([behavior], handler)

response = pipeline(ProcessRequest(data="test"))

# Mypy should know the response type and allow these accesses
value: int = response.value
processed: bool = response.processed

# These should be valid operations on the correct types
if response.processed:
    result: int = response.value + 10
