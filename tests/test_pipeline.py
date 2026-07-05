"""Tests for synchronous pipeline behaviors."""

from collections.abc import Callable
from typing import Any

import pytest

from pymediate import Handler, Request
from pymediate.pipeline import Pipeline, PipelineBehavior


# Fixtures: Request and Response types
class SampleResponse:
    def __init__(self, value: int, log: list[str] | None = None) -> None:
        self.value = value
        self.log = log or []


class SampleRequest(Request[SampleResponse]):
    def __init__(self, value: int) -> None:
        self.value = value


class SampleHandler(Handler[SampleRequest]):
    def __call__(self, request: SampleRequest) -> SampleResponse:
        return SampleResponse(value=request.value * 2)


# Test behaviors
class LoggingBehavior(PipelineBehavior[SampleRequest]):
    """Behavior that logs before and after execution."""

    def __init__(self, log_list: list[str]) -> None:
        self.log_list = log_list

    def __call__(
        self,
        request: SampleRequest,
        next: Callable[[], SampleResponse],
    ) -> SampleResponse:
        self.log_list.append("before")
        response = next()
        self.log_list.append("after")
        return response


class TimingBehavior(PipelineBehavior[SampleRequest]):
    """Behavior that tracks execution."""

    def __init__(self, log_list: list[str]) -> None:
        self.log_list = log_list

    def __call__(
        self,
        request: SampleRequest,
        next: Callable[[], SampleResponse],
    ) -> SampleResponse:
        self.log_list.append("timing_start")
        response = next()
        self.log_list.append("timing_end")
        return response


class ModifyingBehavior(PipelineBehavior[SampleRequest]):
    """Behavior that modifies the response."""

    def __init__(self, multiplier: int) -> None:
        self.multiplier = multiplier

    def __call__(
        self,
        request: SampleRequest,
        next: Callable[[], SampleResponse],
    ) -> SampleResponse:
        response = next()
        response.value *= self.multiplier
        return response


class ValidationBehavior(PipelineBehavior[SampleRequest]):
    """Behavior that validates the request before processing."""

    def __call__(
        self,
        request: SampleRequest,
        next: Callable[[], SampleResponse],
    ) -> SampleResponse:
        if request.value < 0:
            raise ValueError("Value must be non-negative")
        return next()


class ShortCircuitBehavior(PipelineBehavior[SampleRequest]):
    """Behavior that can short-circuit the pipeline."""

    def __init__(self, should_short_circuit: bool) -> None:
        self.should_short_circuit = should_short_circuit

    def __call__(
        self,
        request: SampleRequest,
        next: Callable[[], SampleResponse],
    ) -> SampleResponse:
        if self.should_short_circuit:
            # Don't call next, return early
            return SampleResponse(value=-1)
        return next()


class ExceptionBehavior(PipelineBehavior[SampleRequest]):
    """Behavior that handles exceptions."""

    def __init__(self, log_list: list[str]) -> None:
        self.log_list = log_list

    def __call__(
        self,
        request: SampleRequest,
        next: Callable[[], SampleResponse],
    ) -> SampleResponse:
        try:
            return next()
        except ValueError as e:
            self.log_list.append(f"caught: {e}")
            raise


# Tests
def test_pipeline_with_no_behaviors() -> None:
    """Test that pipeline with no behaviors just calls the handler."""
    handler = SampleHandler()
    pipeline: Pipeline[SampleRequest, SampleResponse] = Pipeline([], handler)

    request = SampleRequest(value=5)
    response = pipeline(request)

    assert response.value == 10  # 5 * 2


def test_pipeline_with_single_behavior() -> None:
    """Test pipeline with a single behavior."""
    log: list[str] = []
    handler = SampleHandler()
    behavior = LoggingBehavior(log)
    pipeline: Pipeline[SampleRequest, SampleResponse] = Pipeline([behavior], handler)

    request = SampleRequest(value=3)
    response = pipeline(request)

    assert response.value == 6  # 3 * 2
    assert log == ["before", "after"]


def test_pipeline_with_multiple_behaviors() -> None:
    """Test pipeline with multiple behaviors in correct order."""
    log: list[str] = []
    handler = SampleHandler()
    logging = LoggingBehavior(log)
    timing = TimingBehavior(log)

    # Order: logging first, then timing
    pipeline: Pipeline[SampleRequest, SampleResponse] = Pipeline([logging, timing], handler)

    request = SampleRequest(value=4)
    response = pipeline(request)

    assert response.value == 8  # 4 * 2
    # Logging wraps timing, so:
    # before (logging) -> timing_start -> handler -> timing_end -> after (logging)
    assert log == ["before", "timing_start", "timing_end", "after"]


def test_pipeline_behavior_execution_order() -> None:
    """Test that behaviors execute in the correct order (left to right)."""
    log: list[str] = []
    handler = SampleHandler()

    class FirstBehavior(PipelineBehavior[SampleRequest]):
        def __call__(
            self,
            request: SampleRequest,
            next: Callable[[], SampleResponse],
        ) -> SampleResponse:
            log.append("first_before")
            response = next()
            log.append("first_after")
            return response

    class SecondBehavior(PipelineBehavior[SampleRequest]):
        def __call__(
            self,
            request: SampleRequest,
            next: Callable[[], SampleResponse],
        ) -> SampleResponse:
            log.append("second_before")
            response = next()
            log.append("second_after")
            return response

    class ThirdBehavior(PipelineBehavior[SampleRequest]):
        def __call__(
            self,
            request: SampleRequest,
            next: Callable[[], SampleResponse],
        ) -> SampleResponse:
            log.append("third_before")
            response = next()
            log.append("third_after")
            return response

    pipeline: Pipeline[SampleRequest, SampleResponse] = Pipeline(
        [FirstBehavior(), SecondBehavior(), ThirdBehavior()],
        handler,
    )

    request = SampleRequest(value=1)
    pipeline(request)

    # First behavior is outermost, third is innermost
    expected = [
        "first_before",
        "second_before",
        "third_before",
        "third_after",
        "second_after",
        "first_after",
    ]
    assert log == expected


def test_pipeline_behavior_can_modify_response() -> None:
    """Test that behaviors can modify the response."""
    handler = SampleHandler()
    multiplier = ModifyingBehavior(3)
    pipeline: Pipeline[SampleRequest, SampleResponse] = Pipeline([multiplier], handler)

    request = SampleRequest(value=5)
    response = pipeline(request)

    # Handler returns 5 * 2 = 10, behavior multiplies by 3
    assert response.value == 30


def test_pipeline_multiple_modifying_behaviors() -> None:
    """Test multiple behaviors that modify the response."""
    handler = SampleHandler()
    multiply_by_2 = ModifyingBehavior(2)
    multiply_by_3 = ModifyingBehavior(3)

    # Order: multiply_by_2 first, then multiply_by_3
    pipeline: Pipeline[SampleRequest, SampleResponse] = Pipeline(
        [multiply_by_2, multiply_by_3], handler
    )

    request = SampleRequest(value=5)
    response = pipeline(request)

    # Handler: 5 * 2 = 10
    # multiply_by_3 (inner): 10 * 3 = 30
    # multiply_by_2 (outer): 30 * 2 = 60
    assert response.value == 60


def test_pipeline_behavior_can_short_circuit() -> None:
    """Test that behavior can short-circuit the pipeline by not calling next."""
    handler = SampleHandler()
    short_circuit = ShortCircuitBehavior(should_short_circuit=True)
    pipeline: Pipeline[SampleRequest, SampleResponse] = Pipeline([short_circuit], handler)

    request = SampleRequest(value=5)
    response = pipeline(request)

    # Handler should not be called, response is from behavior
    assert response.value == -1


def test_pipeline_short_circuit_only_when_needed() -> None:
    """Test that behavior conditionally short-circuits."""
    handler = SampleHandler()

    # First test: no short-circuit
    no_short_circuit = ShortCircuitBehavior(should_short_circuit=False)
    pipeline1: Pipeline[SampleRequest, SampleResponse] = Pipeline([no_short_circuit], handler)
    response1 = pipeline1(SampleRequest(value=5))
    assert response1.value == 10  # Normal handler execution

    # Second test: with short-circuit
    with_short_circuit = ShortCircuitBehavior(should_short_circuit=True)
    pipeline2: Pipeline[SampleRequest, SampleResponse] = Pipeline([with_short_circuit], handler)
    response2 = pipeline2(SampleRequest(value=5))
    assert response2.value == -1  # Short-circuited


def test_pipeline_validation_behavior() -> None:
    """Test validation behavior that checks request before processing."""
    handler = SampleHandler()
    validation = ValidationBehavior()
    pipeline: Pipeline[SampleRequest, SampleResponse] = Pipeline([validation], handler)

    # Valid request should work
    valid_request = SampleRequest(value=5)
    response = pipeline(valid_request)
    assert response.value == 10

    # Invalid request should raise
    invalid_request = SampleRequest(value=-1)
    with pytest.raises(ValueError, match="Value must be non-negative"):
        pipeline(invalid_request)


def test_pipeline_exception_handling_behavior() -> None:
    """Test behavior that handles exceptions from downstream."""
    log: list[str] = []
    handler = SampleHandler()
    validation = ValidationBehavior()
    exception_handler = ExceptionBehavior(log)

    # exception_handler wraps validation
    pipeline: Pipeline[SampleRequest, SampleResponse] = Pipeline(
        [exception_handler, validation], handler
    )

    invalid_request = SampleRequest(value=-1)
    with pytest.raises(ValueError):
        pipeline(invalid_request)

    # Exception should have been caught and re-raised
    assert "caught: Value must be non-negative" in log


def test_pipeline_complex_scenario() -> None:
    """Test complex scenario with multiple behaviors working together."""
    log: list[str] = []
    handler = SampleHandler()

    logging = LoggingBehavior(log)
    timing = TimingBehavior(log)
    validation = ValidationBehavior()
    multiplier = ModifyingBehavior(2)

    # Order: logging -> timing -> validation -> multiplier -> handler
    pipeline: Pipeline[SampleRequest, SampleResponse] = Pipeline(
        [logging, timing, validation, multiplier], handler
    )

    request = SampleRequest(value=3)
    response = pipeline(request)

    # Handler: 3 * 2 = 6
    # Multiplier: 6 * 2 = 12
    assert response.value == 12

    # Check execution order
    assert log == ["before", "timing_start", "timing_end", "after"]


def test_pipeline_with_stateful_behavior() -> None:
    """Test that behaviors can maintain state across multiple calls."""

    class CountingBehavior(PipelineBehavior[SampleRequest]):
        def __init__(self) -> None:
            self.call_count = 0

        def __call__(
            self,
            request: SampleRequest,
            next: Callable[[], SampleResponse],
        ) -> SampleResponse:
            self.call_count += 1
            return next()

    handler = SampleHandler()
    counter = CountingBehavior()
    pipeline: Pipeline[SampleRequest, SampleResponse] = Pipeline([counter], handler)

    # Call pipeline multiple times
    pipeline(SampleRequest(value=1))
    pipeline(SampleRequest(value=2))
    pipeline(SampleRequest(value=3))

    assert counter.call_count == 3


def test_pipeline_type_safety() -> None:
    """Test that pipeline maintains type safety."""
    handler = SampleHandler()
    pipeline: Pipeline[SampleRequest, SampleResponse] = Pipeline([LoggingBehavior([])], handler)

    request = SampleRequest(value=5)
    response = pipeline(request)

    # Response should be of correct type
    assert isinstance(response, SampleResponse)
    assert hasattr(response, "value")


def test_pipeline_behavior_accessing_request() -> None:
    """Test that behaviors can access and use request data."""

    class RequestInspectingBehavior(PipelineBehavior[SampleRequest]):
        def __init__(self, log_list: list[str]) -> None:
            self.log_list = log_list

        def __call__(
            self,
            request: SampleRequest,
            next: Callable[[], SampleResponse],
        ) -> SampleResponse:
            self.log_list.append(f"request_value={request.value}")
            return next()

    log: list[str] = []
    handler = SampleHandler()
    inspector = RequestInspectingBehavior(log)
    pipeline: Pipeline[SampleRequest, SampleResponse] = Pipeline([inspector], handler)

    pipeline(SampleRequest(value=42))

    assert log == ["request_value=42"]


def test_pipeline_behavior_modifying_response_object() -> None:
    """Test that behaviors can modify response object properties."""

    class ResponseLogInjector(PipelineBehavior[SampleRequest]):
        def __call__(
            self,
            request: SampleRequest,
            next: Callable[[], SampleResponse],
        ) -> SampleResponse:
            response = next()
            response.log.append("injected_log")
            return response

    handler = SampleHandler()
    injector = ResponseLogInjector()
    pipeline: Pipeline[SampleRequest, SampleResponse] = Pipeline([injector], handler)

    response = pipeline(SampleRequest(value=1))

    assert "injected_log" in response.log


def test_empty_behaviors_list() -> None:
    """Test that empty behaviors list works correctly."""
    handler = SampleHandler()
    pipeline: Pipeline[SampleRequest, SampleResponse] = Pipeline([], handler)

    response = pipeline(SampleRequest(value=7))
    assert response.value == 14  # 7 * 2, just the handler


def test_pipeline_with_different_request_response_types() -> None:
    """Test pipeline with different request/response type combinations."""

    class StringResponse:
        def __init__(self, message: str) -> None:
            self.message = message

    class StringRequest(Request[StringResponse]):
        def __init__(self, text: str) -> None:
            self.text = text

    class StringHandler(Handler[StringRequest]):
        def __call__(self, request: StringRequest) -> StringResponse:
            return StringResponse(message=request.text.upper())

    class UppercaseBehavior(PipelineBehavior[StringRequest]):
        def __call__(
            self,
            request: StringRequest,
            next: Callable[[], StringResponse],
        ) -> StringResponse:
            response = next()
            response.message = response.message + "!"
            return response

    handler = StringHandler()
    behavior = UppercaseBehavior()
    pipeline: Pipeline[StringRequest, StringResponse] = Pipeline([behavior], handler)

    response = pipeline(StringRequest(text="hello"))
    assert response.message == "HELLO!"


def test_should_apply_universal_behavior_via_bare_request() -> None:
    """PipelineBehavior[Request] (unsubscripted) should apply to any request."""

    class UniversalBehavior(PipelineBehavior[Request]):  # type: ignore[type-arg]
        def __call__(self, request: Request[Any], next: Callable[[], Any]) -> Any:
            return next()

    assert UniversalBehavior.__get_request_type__() is Request
    assert UniversalBehavior.should_apply(SampleRequest(value=1)) is True


def test_get_request_type_fallback_when_not_parameterized() -> None:
    """Subclassing PipelineBehavior directly (no [X] at all) falls back to Request.

    __orig_bases__ is still populated in this case (as (ABC, Generic[RequestT])),
    but none of those bases have PipelineBehavior as their origin, so the lookup
    loop never matches and falls through to the Request fallback.
    """

    class BareBehavior(PipelineBehavior):  # type: ignore[type-arg]
        def __call__(self, request: Request[Any], next: Callable[[], Any]) -> Any:
            return next()

    assert BareBehavior.__get_request_type__() is Request
    assert BareBehavior.should_apply(SampleRequest(value=1)) is True


class BaseSampleRequest(Request[SampleResponse]):
    def __init__(self, value: int) -> None:
        self.value = value


class SubSampleRequest(BaseSampleRequest):
    pass


def test_should_apply_matches_subclasses_by_default() -> None:
    """apply_to_subclasses defaults to True, so a subclass instance matches too."""

    class InheritingBehavior(PipelineBehavior[BaseSampleRequest]):
        def __call__(self, request: BaseSampleRequest, next: Callable[[], Any]) -> Any:
            return next()

    assert InheritingBehavior.apply_to_subclasses is True
    assert InheritingBehavior.should_apply(SubSampleRequest(value=1)) is True


def test_should_apply_respects_apply_to_subclasses_false() -> None:
    """apply_to_subclasses=False restricts matching to the exact registered type."""

    class ExactOnlyBehavior(PipelineBehavior[BaseSampleRequest]):
        apply_to_subclasses = False

        def __call__(self, request: BaseSampleRequest, next: Callable[[], Any]) -> Any:
            return next()

    assert ExactOnlyBehavior.should_apply(BaseSampleRequest(value=1)) is True
    assert ExactOnlyBehavior.should_apply(SubSampleRequest(value=1)) is False
