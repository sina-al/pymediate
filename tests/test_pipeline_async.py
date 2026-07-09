"""Tests for asynchronous pipeline behaviors."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import pytest

from pymediate import Request
from pymediate._internal.pipeline import compose_async
from pymediate.aio import Handler
from pymediate.aio.pipeline import PipelineBehavior


# Test fixtures: Request and Response types
class SampleResponse:
    def __init__(self, value: int, log: list[str] | None = None) -> None:
        self.value = value
        self.log = log or []


class SampleRequest(Request[SampleResponse]):
    def __init__(self, value: int) -> None:
        self.value = value


class SampleHandler(Handler[SampleRequest]):
    async def __call__(self, request: SampleRequest) -> SampleResponse:
        # Simulate async operation
        await asyncio.sleep(0.001)
        return SampleResponse(value=request.value * 2)


# Test behaviors
class AsyncLoggingBehavior(PipelineBehavior[SampleRequest]):
    """Async behavior that logs before and after execution."""

    def __init__(self, log_list: list[str]) -> None:
        self.log_list = log_list

    async def __call__(
        self,
        request: SampleRequest,
        next: Callable[[], Awaitable[SampleResponse]],
    ) -> SampleResponse:
        self.log_list.append("before")
        response = await next()
        self.log_list.append("after")
        return response


class AsyncTimingBehavior(PipelineBehavior[SampleRequest]):
    """Async behavior that tracks execution."""

    def __init__(self, log_list: list[str]) -> None:
        self.log_list = log_list

    async def __call__(
        self,
        request: SampleRequest,
        next: Callable[[], Awaitable[SampleResponse]],
    ) -> SampleResponse:
        self.log_list.append("timing_start")
        response = await next()
        self.log_list.append("timing_end")
        return response


class AsyncModifyingBehavior(PipelineBehavior[SampleRequest]):
    """Async behavior that modifies the response."""

    def __init__(self, multiplier: int) -> None:
        self.multiplier = multiplier

    async def __call__(
        self,
        request: SampleRequest,
        next: Callable[[], Awaitable[SampleResponse]],
    ) -> SampleResponse:
        response = await next()
        await asyncio.sleep(0.001)  # Simulate async work
        response.value *= self.multiplier
        return response


class AsyncValidationBehavior(PipelineBehavior[SampleRequest]):
    """Async behavior that validates the request before processing."""

    async def __call__(
        self,
        request: SampleRequest,
        next: Callable[[], Awaitable[SampleResponse]],
    ) -> SampleResponse:
        # Simulate async validation (e.g., database check)
        await asyncio.sleep(0.001)
        if request.value < 0:
            raise ValueError("Value must be non-negative")
        return await next()


class AsyncShortCircuitBehavior(PipelineBehavior[SampleRequest]):
    """Async behavior that can short-circuit the pipeline."""

    def __init__(self, should_short_circuit: bool) -> None:
        self.should_short_circuit = should_short_circuit

    async def __call__(
        self,
        request: SampleRequest,
        next: Callable[[], Awaitable[SampleResponse]],
    ) -> SampleResponse:
        if self.should_short_circuit:
            # Don't call next, return early
            await asyncio.sleep(0.001)
            return SampleResponse(value=-1)
        return await next()


class AsyncExceptionBehavior(PipelineBehavior[SampleRequest]):
    """Async behavior that handles exceptions."""

    def __init__(self, log_list: list[str]) -> None:
        self.log_list = log_list

    async def __call__(
        self,
        request: SampleRequest,
        next: Callable[[], Awaitable[SampleResponse]],
    ) -> SampleResponse:
        try:
            return await next()
        except ValueError as e:
            self.log_list.append(f"caught: {e}")
            raise


class AsyncCachingBehavior(PipelineBehavior[SampleRequest]):
    """Async behavior that caches responses."""

    def __init__(self) -> None:
        self.cache: dict[int, SampleResponse] = {}

    async def __call__(
        self,
        request: SampleRequest,
        next: Callable[[], Awaitable[SampleResponse]],
    ) -> SampleResponse:
        # Check cache
        if request.value in self.cache:
            return self.cache[request.value]

        # Execute and cache
        response = await next()
        self.cache[request.value] = response
        return response


# Tests
@pytest.mark.asyncio
async def test_async_pipeline_with_no_behaviors() -> None:
    """Test that async pipeline with no behaviors just calls the handler."""
    handler = SampleHandler()
    pipeline = compose_async([], handler)

    request = SampleRequest(value=5)
    response = await pipeline(request)

    assert response.value == 10  # 5 * 2


@pytest.mark.asyncio
async def test_async_pipeline_with_single_behavior() -> None:
    """Test async pipeline with a single behavior."""
    log: list[str] = []
    handler = SampleHandler()
    behavior = AsyncLoggingBehavior(log)
    pipeline = compose_async([behavior], handler)

    request = SampleRequest(value=3)
    response = await pipeline(request)

    assert response.value == 6  # 3 * 2
    assert log == ["before", "after"]


@pytest.mark.asyncio
async def test_async_pipeline_with_multiple_behaviors() -> None:
    """Test async pipeline with multiple behaviors in correct order."""
    log: list[str] = []
    handler = SampleHandler()
    logging = AsyncLoggingBehavior(log)
    timing = AsyncTimingBehavior(log)

    # Order: logging first, then timing
    pipeline = compose_async([logging, timing], handler)

    request = SampleRequest(value=4)
    response = await pipeline(request)

    assert response.value == 8  # 4 * 2
    # Logging wraps timing, so:
    # before (logging) -> timing_start -> handler -> timing_end -> after (logging)
    assert log == ["before", "timing_start", "timing_end", "after"]


@pytest.mark.asyncio
async def test_async_pipeline_behavior_execution_order() -> None:
    """Test that async behaviors execute in the correct order (left to right)."""
    log: list[str] = []
    handler = SampleHandler()

    class FirstBehavior(PipelineBehavior[SampleRequest]):
        async def __call__(
            self,
            request: SampleRequest,
            next: Callable[[], Awaitable[SampleResponse]],
        ) -> SampleResponse:
            log.append("first_before")
            response = await next()
            log.append("first_after")
            return response

    class SecondBehavior(PipelineBehavior[SampleRequest]):
        async def __call__(
            self,
            request: SampleRequest,
            next: Callable[[], Awaitable[SampleResponse]],
        ) -> SampleResponse:
            log.append("second_before")
            response = await next()
            log.append("second_after")
            return response

    class ThirdBehavior(PipelineBehavior[SampleRequest]):
        async def __call__(
            self,
            request: SampleRequest,
            next: Callable[[], Awaitable[SampleResponse]],
        ) -> SampleResponse:
            log.append("third_before")
            response = await next()
            log.append("third_after")
            return response

    pipeline = compose_async(
        [FirstBehavior(), SecondBehavior(), ThirdBehavior()],
        handler,
    )

    request = SampleRequest(value=1)
    await pipeline(request)

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


@pytest.mark.asyncio
async def test_async_pipeline_behavior_can_modify_response() -> None:
    """Test that async behaviors can modify the response."""
    handler = SampleHandler()
    multiplier = AsyncModifyingBehavior(3)
    pipeline = compose_async([multiplier], handler)

    request = SampleRequest(value=5)
    response = await pipeline(request)

    # Handler returns 5 * 2 = 10, behavior multiplies by 3
    assert response.value == 30


@pytest.mark.asyncio
async def test_async_pipeline_multiple_modifying_behaviors() -> None:
    """Test multiple async behaviors that modify the response."""
    handler = SampleHandler()
    multiply_by_2 = AsyncModifyingBehavior(2)
    multiply_by_3 = AsyncModifyingBehavior(3)

    # Order: multiply_by_2 first, then multiply_by_3
    pipeline = compose_async([multiply_by_2, multiply_by_3], handler)

    request = SampleRequest(value=5)
    response = await pipeline(request)

    # Handler: 5 * 2 = 10
    # multiply_by_3 (inner): 10 * 3 = 30
    # multiply_by_2 (outer): 30 * 2 = 60
    assert response.value == 60


@pytest.mark.asyncio
async def test_async_pipeline_behavior_can_short_circuit() -> None:
    """Test that async behavior can short-circuit the pipeline by not calling next."""
    handler = SampleHandler()
    short_circuit = AsyncShortCircuitBehavior(should_short_circuit=True)
    pipeline = compose_async([short_circuit], handler)

    request = SampleRequest(value=5)
    response = await pipeline(request)

    # Handler should not be called, response is from behavior
    assert response.value == -1


@pytest.mark.asyncio
async def test_async_pipeline_short_circuit_only_when_needed() -> None:
    """Test that async behavior conditionally short-circuits."""
    handler = SampleHandler()

    # First test: no short-circuit
    no_short_circuit = AsyncShortCircuitBehavior(should_short_circuit=False)
    pipeline1 = compose_async([no_short_circuit], handler)
    response1 = await pipeline1(SampleRequest(value=5))
    assert response1.value == 10  # Normal handler execution

    # Second test: with short-circuit
    with_short_circuit = AsyncShortCircuitBehavior(should_short_circuit=True)
    pipeline2 = compose_async([with_short_circuit], handler)
    response2 = await pipeline2(SampleRequest(value=5))
    assert response2.value == -1  # Short-circuited


@pytest.mark.asyncio
async def test_async_pipeline_validation_behavior() -> None:
    """Test async validation behavior that checks request before processing."""
    handler = SampleHandler()
    validation = AsyncValidationBehavior()
    pipeline = compose_async([validation], handler)

    # Valid request should work
    valid_request = SampleRequest(value=5)
    response = await pipeline(valid_request)
    assert response.value == 10

    # Invalid request should raise
    invalid_request = SampleRequest(value=-1)
    with pytest.raises(ValueError, match="Value must be non-negative"):
        await pipeline(invalid_request)


@pytest.mark.asyncio
async def test_async_pipeline_exception_handling_behavior() -> None:
    """Test async behavior that handles exceptions from downstream."""
    log: list[str] = []
    handler = SampleHandler()
    validation = AsyncValidationBehavior()
    exception_handler = AsyncExceptionBehavior(log)

    # exception_handler wraps validation
    pipeline = compose_async([exception_handler, validation], handler)

    invalid_request = SampleRequest(value=-1)
    with pytest.raises(ValueError):
        await pipeline(invalid_request)

    # Exception should have been caught and re-raised
    assert "caught: Value must be non-negative" in log


@pytest.mark.asyncio
async def test_async_pipeline_caching_behavior() -> None:
    """Test async caching behavior."""
    handler = SampleHandler()
    cache = AsyncCachingBehavior()
    pipeline = compose_async([cache], handler)

    # First call - should hit handler
    response1 = await pipeline(SampleRequest(value=5))
    assert response1.value == 10

    # Second call with same value - should hit cache
    response2 = await pipeline(SampleRequest(value=5))
    assert response2.value == 10

    # Verify it's the same cached instance
    assert response1 is response2


@pytest.mark.asyncio
async def test_async_pipeline_complex_scenario() -> None:
    """Test complex async scenario with multiple behaviors working together."""
    log: list[str] = []
    handler = SampleHandler()

    logging = AsyncLoggingBehavior(log)
    timing = AsyncTimingBehavior(log)
    validation = AsyncValidationBehavior()
    multiplier = AsyncModifyingBehavior(2)

    # Order: logging -> timing -> validation -> multiplier -> handler
    pipeline = compose_async([logging, timing, validation, multiplier], handler)

    request = SampleRequest(value=3)
    response = await pipeline(request)

    # Handler: 3 * 2 = 6
    # Multiplier: 6 * 2 = 12
    assert response.value == 12

    # Check execution order
    assert log == ["before", "timing_start", "timing_end", "after"]


@pytest.mark.asyncio
async def test_async_pipeline_with_stateful_behavior() -> None:
    """Test that async behaviors can maintain state across multiple calls."""

    class AsyncCountingBehavior(PipelineBehavior[SampleRequest]):
        def __init__(self) -> None:
            self.call_count = 0

        async def __call__(
            self,
            request: SampleRequest,
            next: Callable[[], Awaitable[SampleResponse]],
        ) -> SampleResponse:
            self.call_count += 1
            await asyncio.sleep(0.001)
            return await next()

    handler = SampleHandler()
    counter = AsyncCountingBehavior()
    pipeline = compose_async([counter], handler)

    # Call pipeline multiple times
    await pipeline(SampleRequest(value=1))
    await pipeline(SampleRequest(value=2))
    await pipeline(SampleRequest(value=3))

    assert counter.call_count == 3


@pytest.mark.asyncio
async def test_async_pipeline_type_safety() -> None:
    """Test that async pipeline maintains type safety."""
    handler = SampleHandler()
    pipeline = compose_async([AsyncLoggingBehavior([])], handler)

    request = SampleRequest(value=5)
    response = await pipeline(request)

    # Response should be of correct type
    assert isinstance(response, SampleResponse)
    assert hasattr(response, "value")


@pytest.mark.asyncio
async def test_async_pipeline_behavior_accessing_request() -> None:
    """Test that async behaviors can access and use request data."""

    class AsyncRequestInspectingBehavior(PipelineBehavior[SampleRequest]):
        def __init__(self, log_list: list[str]) -> None:
            self.log_list = log_list

        async def __call__(
            self,
            request: SampleRequest,
            next: Callable[[], Awaitable[SampleResponse]],
        ) -> SampleResponse:
            self.log_list.append(f"request_value={request.value}")
            return await next()

    log: list[str] = []
    handler = SampleHandler()
    inspector = AsyncRequestInspectingBehavior(log)
    pipeline = compose_async([inspector], handler)

    await pipeline(SampleRequest(value=42))

    assert log == ["request_value=42"]


@pytest.mark.asyncio
async def test_async_pipeline_concurrent_requests() -> None:
    """Test that async pipeline can handle concurrent requests."""
    handler = SampleHandler()
    cache = AsyncCachingBehavior()
    pipeline = compose_async([cache], handler)

    # Execute multiple requests concurrently
    results = await asyncio.gather(
        pipeline(SampleRequest(value=1)),
        pipeline(SampleRequest(value=2)),
        pipeline(SampleRequest(value=3)),
    )

    assert results[0].value == 2  # 1 * 2
    assert results[1].value == 4  # 2 * 2
    assert results[2].value == 6  # 3 * 2

    # Now execute same request again - should hit cache
    cached_result = await pipeline(SampleRequest(value=1))
    assert cached_result.value == 2
    assert cached_result is results[0]


@pytest.mark.asyncio
async def test_empty_behaviors_list_async() -> None:
    """Test that empty behaviors list works correctly with async."""
    handler = SampleHandler()
    pipeline = compose_async([], handler)

    response = await pipeline(SampleRequest(value=7))
    assert response.value == 14  # 7 * 2, just the handler


@pytest.mark.asyncio
async def test_async_pipeline_with_different_request_response_types() -> None:
    """Test async pipeline with different request/response type combinations."""

    class StringResponse:
        def __init__(self, message: str) -> None:
            self.message = message

    class StringRequest(Request[StringResponse]):
        def __init__(self, text: str) -> None:
            self.text = text

    class StringHandler(Handler[StringRequest]):
        async def __call__(self, request: StringRequest) -> StringResponse:
            await asyncio.sleep(0.001)
            return StringResponse(message=request.text.upper())

    class AsyncUppercaseBehavior(PipelineBehavior[StringRequest]):
        async def __call__(
            self,
            request: StringRequest,
            next: Callable[[], Awaitable[StringResponse]],
        ) -> StringResponse:
            response = await next()
            response.message = response.message + "!"
            return response

    handler = StringHandler()
    behavior = AsyncUppercaseBehavior()
    pipeline = compose_async([behavior], handler)

    response = await pipeline(StringRequest(text="hello"))
    assert response.message == "HELLO!"


@pytest.mark.asyncio
async def test_async_pipeline_behavior_with_async_io_operations() -> None:
    """Test async behavior that performs actual async I/O operations."""

    class AsyncIOBehavior(PipelineBehavior[SampleRequest]):
        def __init__(self, log_list: list[str]) -> None:
            self.log_list = log_list

        async def __call__(
            self,
            request: SampleRequest,
            next: Callable[[], Awaitable[SampleResponse]],
        ) -> SampleResponse:
            # Simulate async I/O (e.g., logging to database)
            await asyncio.sleep(0.01)
            self.log_list.append("io_before")

            response = await next()

            # Simulate more async I/O
            await asyncio.sleep(0.01)
            self.log_list.append("io_after")

            return response

    log: list[str] = []
    handler = SampleHandler()
    io_behavior = AsyncIOBehavior(log)
    pipeline = compose_async([io_behavior], handler)

    response = await pipeline(SampleRequest(value=3))

    assert response.value == 6
    assert log == ["io_before", "io_after"]


def test_should_apply_universal_behavior_via_bare_request() -> None:
    """PipelineBehavior[Request] (unsubscripted) should apply to any request."""

    class UniversalBehavior(PipelineBehavior[Request]):  # type: ignore[type-arg]
        async def __call__(self, request: Request[Any], next: Callable[[], Awaitable[Any]]) -> Any:
            return await next()

    assert UniversalBehavior.__request_type__ is Request
    assert UniversalBehavior.should_apply(SampleRequest(value=1)) is True


def test_should_apply_subscripted_generic_request_type() -> None:
    """PipelineBehavior[Request[Any]] checks isinstance against the generic's origin."""

    class SubscriptedBehavior(PipelineBehavior[Request[Any]]):
        async def __call__(self, request: Request[Any], next: Callable[[], Awaitable[Any]]) -> Any:
            return await next()

    assert SubscriptedBehavior.__request_type__ == Request[Any]
    assert SubscriptedBehavior.should_apply(SampleRequest(value=1)) is True


def test_get_request_type_fallback_when_not_parameterized() -> None:
    """Subclassing PipelineBehavior directly (no [X] at all) falls back to Request.

    __orig_bases__ is still populated in this case (as (ABC, Generic[RequestT])),
    but none of those bases have PipelineBehavior as their origin, so the lookup
    loop never matches and falls through to the Request fallback.
    """

    class BareBehavior(PipelineBehavior):  # type: ignore[type-arg]
        async def __call__(self, request: Request[Any], next: Callable[[], Awaitable[Any]]) -> Any:
            return await next()

    assert BareBehavior.__request_type__ is Request
    assert BareBehavior.should_apply(SampleRequest(value=1)) is True


class BaseSampleRequest(Request[SampleResponse]):
    def __init__(self, value: int) -> None:
        self.value = value


class SubSampleRequest(BaseSampleRequest):
    pass


def test_should_apply_matches_subclasses_by_default() -> None:
    """apply_to_subclasses defaults to True, so a subclass instance matches too."""

    class InheritingBehavior(PipelineBehavior[BaseSampleRequest]):
        async def __call__(
            self, request: BaseSampleRequest, next: Callable[[], Awaitable[Any]]
        ) -> Any:
            return await next()

    assert InheritingBehavior.apply_to_subclasses is True
    assert InheritingBehavior.should_apply(SubSampleRequest(value=1)) is True


def test_should_apply_respects_apply_to_subclasses_false() -> None:
    """apply_to_subclasses=False restricts matching to the exact registered type."""

    class ExactOnlyBehavior(PipelineBehavior[BaseSampleRequest]):
        apply_to_subclasses = False

        async def __call__(
            self, request: BaseSampleRequest, next: Callable[[], Awaitable[Any]]
        ) -> Any:
            return await next()

    assert ExactOnlyBehavior.should_apply(BaseSampleRequest(value=1)) is True
    assert ExactOnlyBehavior.should_apply(SubSampleRequest(value=1)) is False
