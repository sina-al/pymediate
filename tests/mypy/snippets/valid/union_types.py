"""Union types and type narrowing - should pass mypy."""

from dataclasses import dataclass

from pymediate import Handler, Mediator, Request, ServiceCollection


@dataclass
class SuccessResult:
    value: int


@dataclass
class ErrorResult:
    error_message: str


# Union response type
ResultResponse = SuccessResult | ErrorResult


@dataclass
class CalculateRequest(Request[ResultResponse]):
    numerator: int
    denominator: int


class CalculateHandler(Handler[CalculateRequest]):
    def __call__(self, request: CalculateRequest) -> ResultResponse:
        if request.denominator == 0:
            return ErrorResult(error_message="Division by zero")
        return SuccessResult(value=request.numerator // request.denominator)


# Usage
services = ServiceCollection()
services.add(CalculateRequest, CalculateHandler())
provider = services.build_provider()
mediator = Mediator(provider)

request = CalculateRequest(numerator=10, denominator=2)
response = mediator.send(request)

# Type narrowing with isinstance
if isinstance(response, SuccessResult):
    value: int = response.value
elif isinstance(response, ErrorResult):
    error: str = response.error_message
