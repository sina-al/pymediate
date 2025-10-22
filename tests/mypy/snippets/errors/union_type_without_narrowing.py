"""Accessing union type field without type narrowing - should fail mypy."""

from dataclasses import dataclass

from pymediate import Handler, Mediator, Request, SimpleResolver


@dataclass
class SuccessResult:
    value: int


@dataclass
class ErrorResult:
    error_message: str


ResultResponse = SuccessResult | ErrorResult


@dataclass
class CalculateRequest(Request[ResultResponse]):
    x: int


class CalculateHandler(Handler[CalculateRequest]):
    def __call__(self, request: CalculateRequest) -> ResultResponse:
        return SuccessResult(value=request.x * 2)


resolver = SimpleResolver()
resolver.register(CalculateRequest, CalculateHandler())
mediator = Mediator(resolver)

request = CalculateRequest(x=5)
response = mediator.send(request)

# ERROR: Cannot access 'value' without narrowing type
value = response.value

# ERROR: Cannot access 'error_message' without narrowing type
error = response.error_message
