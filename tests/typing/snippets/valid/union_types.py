"""Union types and type narrowing - should pass mypy."""

from dataclasses import dataclass
from typing import override

from pymediate import Handler, Mediator, Request, Services


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
    @override
    def __call__(self, request: CalculateRequest) -> ResultResponse:
        if request.denominator == 0:
            return ErrorResult(error_message="Division by zero")
        return SuccessResult(value=request.numerator // request.denominator)


# Usage
provider = Services().add(CalculateHandler()).provider()
mediator = Mediator(provider)

request = CalculateRequest(numerator=10, denominator=2)
response = mediator.send(request)

# Type narrowing with isinstance: after ruling out SuccessResult, the checker
# should narrow the else branch to ErrorResult on its own
if isinstance(response, SuccessResult):
    value: int = response.value
else:
    error: str = response.error_message
