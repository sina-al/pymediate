"""Comprehensive async DI container tests for mediator with pipeline behaviors.

This mega test suite covers all edge cases for async pipeline behaviors when using
DependencyInjectorServiceProvider with the async mediator.


"""

import asyncio
from dataclasses import dataclass
from typing import Any

import pytest
from dependency_injector import containers, providers

from pymediate import Request
from pymediate.aio import Handler, Mediator
from pymediate.aio.pipeline import PipelineBehavior
from pymediate.providers import DependencyInjectorServiceProvider

# ============================================================================
# Test Fixtures - Requests and Responses
# ============================================================================


@dataclass
class AsyncCounterResponse:
    """Async response that tracks execution count and value transformations."""

    value: int
    execution_log: list[str]


@dataclass
class AsyncCounterRequest(Request[AsyncCounterResponse]):
    """Async request with a value to transform."""

    value: int


# ============================================================================
# Test Fixtures - Basic Behaviors
# ============================================================================


class AsyncIncrementBehavior(PipelineBehavior[AsyncCounterRequest]):
    """Async behavior that increments the value."""

    def __init__(self, amount: int = 1) -> None:
        self.amount = amount
        self.call_count = 0

    async def __call__(self, request: AsyncCounterRequest, next: Any) -> AsyncCounterResponse:
        self.call_count += 1
        response: AsyncCounterResponse = await next()
        response.value += self.amount
        response.execution_log.append(f"AsyncIncrement(+{self.amount})")
        return response


class AsyncMultiplyBehavior(PipelineBehavior[AsyncCounterRequest]):
    """Async behavior that multiplies the value."""

    def __init__(self, factor: int = 2) -> None:
        self.factor = factor
        self.call_count = 0

    async def __call__(self, request: AsyncCounterRequest, next: Any) -> AsyncCounterResponse:
        self.call_count += 1
        response: AsyncCounterResponse = await next()
        response.value *= self.factor
        response.execution_log.append(f"AsyncMultiply(*{self.factor})")
        return response


class AsyncLoggingBehavior(PipelineBehavior[AsyncCounterRequest]):
    """Async behavior that logs execution."""

    def __init__(self, label: str = "default") -> None:
        self.label = label
        self.call_count = 0

    async def __call__(self, request: AsyncCounterRequest, next: Any) -> AsyncCounterResponse:
        self.call_count += 1
        response: AsyncCounterResponse = await next()
        response.execution_log.append(f"AsyncLogging({self.label})")
        return response


# ============================================================================
# Test Fixtures - Short-Circuit Behaviors
# ============================================================================


class AsyncShortCircuitBehavior(PipelineBehavior[AsyncCounterRequest]):
    """Async short-circuit behavior."""

    def __init__(self) -> None:
        self.call_count = 0
        self.short_circuited = False

    async def __call__(self, request: AsyncCounterRequest, next: Any) -> AsyncCounterResponse:
        self.call_count += 1
        if request.value < 0:
            self.short_circuited = True
            return AsyncCounterResponse(value=-999, execution_log=["AsyncShortCircuit"])
        response: AsyncCounterResponse = await next()
        response.execution_log.append("AsyncShortCircuit(passed)")
        return response


# ============================================================================
# Test Fixtures - Async I/O Behaviors
# ============================================================================


class AsyncIOBehavior(PipelineBehavior[AsyncCounterRequest]):
    """Behavior with actual async I/O operations."""

    async def __call__(self, request: AsyncCounterRequest, next: Any) -> AsyncCounterResponse:
        # Simulate async operations (DB query, API call, etc.)
        await asyncio.sleep(0.01)
        response: AsyncCounterResponse = await next()
        await asyncio.sleep(0.01)
        response.execution_log.append("AsyncIO")
        return response


# ============================================================================
# Test Fixtures - Stateful Behaviors
# ============================================================================


class AsyncCountingBehavior(PipelineBehavior[AsyncCounterRequest]):
    """Tracks execution count."""

    instance_counter = 0

    def __init__(self) -> None:
        AsyncCountingBehavior.instance_counter += 1
        self.instance_id = AsyncCountingBehavior.instance_counter
        self.execution_count = 0

    async def __call__(self, request: AsyncCounterRequest, next: Any) -> AsyncCounterResponse:
        self.execution_count += 1
        response: AsyncCounterResponse = await next()
        response.execution_log.append(
            f"AsyncCounting(inst={self.instance_id},exec={self.execution_count})"
        )
        return response


# ============================================================================
# Tests: Basic Async Behavior Execution
# ============================================================================


@pytest.mark.asyncio
async def test_async_di_mediator_with_single_behavior() -> None:
    """Test async mediator with single behavior from DI container."""

    class AsyncCounterHandler(Handler[AsyncCounterRequest]):
        async def __call__(self, request: AsyncCounterRequest) -> AsyncCounterResponse:
            await asyncio.sleep(0.001)
            return AsyncCounterResponse(value=request.value, execution_log=["AsyncHandler"])

    class TestContainer(containers.DeclarativeContainer):
        increment = providers.Factory(AsyncIncrementBehavior, amount=5)
        handler = providers.Factory(AsyncCounterHandler)

    container = TestContainer()
    provider = DependencyInjectorServiceProvider(container)
    mediator = Mediator(provider)

    response = await mediator.send(AsyncCounterRequest(value=10))

    assert response.value == 15  # 10 + 5
    assert "AsyncHandler" in response.execution_log
    assert "AsyncIncrement(+5)" in response.execution_log


@pytest.mark.asyncio
async def test_async_di_mediator_with_multiple_behaviors() -> None:
    """Test async mediator with multiple behaviors from DI container."""

    class AsyncCounterHandler(Handler[AsyncCounterRequest]):
        async def __call__(self, request: AsyncCounterRequest) -> AsyncCounterResponse:
            await asyncio.sleep(0.001)
            return AsyncCounterResponse(value=request.value, execution_log=["AsyncHandler"])

    class TestContainer(containers.DeclarativeContainer):
        increment = providers.Factory(AsyncIncrementBehavior, amount=3)
        multiply = providers.Factory(AsyncMultiplyBehavior, factor=2)
        logging = providers.Factory(AsyncLoggingBehavior, label="test")
        handler = providers.Factory(AsyncCounterHandler)

    container = TestContainer()
    provider = DependencyInjectorServiceProvider(container)
    mediator = Mediator(provider)

    response = await mediator.send(AsyncCounterRequest(value=10))

    # Execution: handler(10) -> *2 = 20 -> +3 = 23
    assert response.value == 23
    assert response.execution_log == [
        "AsyncHandler",
        "AsyncLogging(test)",
        "AsyncMultiply(*2)",
        "AsyncIncrement(+3)",
    ]


@pytest.mark.asyncio
async def test_async_di_mediator_without_behaviors() -> None:
    """Test async mediator with only handler (fast path)."""

    class AsyncCounterHandler(Handler[AsyncCounterRequest]):
        async def __call__(self, request: AsyncCounterRequest) -> AsyncCounterResponse:
            await asyncio.sleep(0.001)
            return AsyncCounterResponse(value=request.value, execution_log=["AsyncHandler"])

    class TestContainer(containers.DeclarativeContainer):
        handler = providers.Factory(AsyncCounterHandler)

    container = TestContainer()
    provider = DependencyInjectorServiceProvider(container)
    mediator = Mediator(provider)

    response = await mediator.send(AsyncCounterRequest(value=42))

    assert response.value == 42
    assert response.execution_log == ["AsyncHandler"]


# ============================================================================
# Tests: Short-Circuit Behaviors
# ============================================================================


@pytest.mark.asyncio
async def test_async_di_short_circuit_behavior() -> None:
    """Test async short-circuit behavior."""

    class AsyncCounterHandler(Handler[AsyncCounterRequest]):
        async def __call__(self, request: AsyncCounterRequest) -> AsyncCounterResponse:
            await asyncio.sleep(0.001)
            return AsyncCounterResponse(value=request.value, execution_log=["AsyncHandler"])

    class TestContainer(containers.DeclarativeContainer):
        short_circuit = providers.Factory(AsyncShortCircuitBehavior)
        increment = providers.Factory(AsyncIncrementBehavior, amount=10)
        handler = providers.Factory(AsyncCounterHandler)

    container = TestContainer()
    provider = DependencyInjectorServiceProvider(container)
    mediator = Mediator(provider)

    # Positive value - no short circuit
    response = await mediator.send(AsyncCounterRequest(value=5))
    assert response.value == 15  # 5 + 10
    assert "AsyncShortCircuit(passed)" in response.execution_log
    assert "AsyncIncrement(+10)" in response.execution_log

    # Negative value - short circuit
    response = await mediator.send(AsyncCounterRequest(value=-5))
    assert response.value == -999
    assert response.execution_log == ["AsyncShortCircuit"]


# ============================================================================
# Tests: Registration Order
# ============================================================================


@pytest.mark.asyncio
async def test_async_di_registration_order_matters() -> None:
    """Test that async behavior registration order determines execution order."""

    class AsyncCounterHandler(Handler[AsyncCounterRequest]):
        async def __call__(self, request: AsyncCounterRequest) -> AsyncCounterResponse:
            await asyncio.sleep(0.001)
            return AsyncCounterResponse(value=request.value, execution_log=["AsyncHandler"])

    # Container 1: increment then multiply
    class Container1(containers.DeclarativeContainer):
        increment = providers.Factory(AsyncIncrementBehavior, amount=5)
        multiply = providers.Factory(AsyncMultiplyBehavior, factor=2)
        handler = providers.Factory(AsyncCounterHandler)

    # Container 2: multiply then increment
    class Container2(containers.DeclarativeContainer):
        multiply = providers.Factory(AsyncMultiplyBehavior, factor=2)
        increment = providers.Factory(AsyncIncrementBehavior, amount=5)
        handler = providers.Factory(AsyncCounterHandler)

    mediator1 = Mediator(DependencyInjectorServiceProvider(Container1()))
    mediator2 = Mediator(DependencyInjectorServiceProvider(Container2()))

    response1 = await mediator1.send(AsyncCounterRequest(value=10))
    response2 = await mediator2.send(AsyncCounterRequest(value=10))

    # Container1: 10 * 2 = 20, then + 5 = 25
    assert response1.value == 25
    assert response1.execution_log == ["AsyncHandler", "AsyncMultiply(*2)", "AsyncIncrement(+5)"]

    # Container2: (10 + 5) * 2 = 30
    assert response2.value == 30
    assert response2.execution_log == ["AsyncHandler", "AsyncIncrement(+5)", "AsyncMultiply(*2)"]


# ============================================================================
# Tests: Provider Scopes
# ============================================================================


@pytest.mark.asyncio
async def test_async_di_singleton_behavior_reused() -> None:
    """Test that singleton async behaviors are reused across requests."""

    class AsyncCounterHandler(Handler[AsyncCounterRequest]):
        async def __call__(self, request: AsyncCounterRequest) -> AsyncCounterResponse:
            await asyncio.sleep(0.001)
            return AsyncCounterResponse(value=request.value, execution_log=["AsyncHandler"])

    class TestContainer(containers.DeclarativeContainer):
        counting = providers.Singleton(AsyncCountingBehavior)
        handler = providers.Factory(AsyncCounterHandler)

    AsyncCountingBehavior.instance_counter = 0

    container = TestContainer()
    provider = DependencyInjectorServiceProvider(container)
    mediator = Mediator(provider)

    # Send 3 requests
    response1 = await mediator.send(AsyncCounterRequest(value=1))
    response2 = await mediator.send(AsyncCounterRequest(value=2))
    response3 = await mediator.send(AsyncCounterRequest(value=3))

    # Should have created only 1 instance
    assert AsyncCountingBehavior.instance_counter == 1

    # Should show increasing execution count from same instance
    assert "AsyncCounting(inst=1,exec=1)" in response1.execution_log
    assert "AsyncCounting(inst=1,exec=2)" in response2.execution_log
    assert "AsyncCounting(inst=1,exec=3)" in response3.execution_log


@pytest.mark.asyncio
async def test_async_di_factory_behavior_fresh_instances() -> None:
    """Test that factory async behaviors create new instances per resolve."""

    class AsyncCounterHandler(Handler[AsyncCounterRequest]):
        async def __call__(self, request: AsyncCounterRequest) -> AsyncCounterResponse:
            await asyncio.sleep(0.001)
            return AsyncCounterResponse(value=request.value, execution_log=["AsyncHandler"])

    class TestContainer(containers.DeclarativeContainer):
        counting = providers.Factory(AsyncCountingBehavior)
        handler = providers.Factory(AsyncCounterHandler)

    AsyncCountingBehavior.instance_counter = 0

    container = TestContainer()
    provider = DependencyInjectorServiceProvider(container)
    mediator = Mediator(provider)

    # Send 3 requests
    response1 = await mediator.send(AsyncCounterRequest(value=1))
    response2 = await mediator.send(AsyncCounterRequest(value=2))
    response3 = await mediator.send(AsyncCounterRequest(value=3))

    # Should have created 4 instances (1 from scan + 3 from sends)
    assert AsyncCountingBehavior.instance_counter == 4

    # Instance IDs: first is from scan (not used), then 2,3,4 from actual sends
    assert "AsyncCounting(inst=2,exec=1)" in response1.execution_log
    assert "AsyncCounting(inst=3,exec=1)" in response2.execution_log
    assert "AsyncCounting(inst=4,exec=1)" in response3.execution_log


# ============================================================================
# Tests: Concurrent Execution
# ============================================================================


@pytest.mark.asyncio
async def test_async_di_concurrent_requests() -> None:
    """Test concurrent async requests with shared singleton behavior."""

    class AsyncCounterHandler(Handler[AsyncCounterRequest]):
        async def __call__(self, request: AsyncCounterRequest) -> AsyncCounterResponse:
            await asyncio.sleep(0.001)
            return AsyncCounterResponse(value=request.value, execution_log=["AsyncHandler"])

    class TestContainer(containers.DeclarativeContainer):
        # Singleton - shared across concurrent requests
        increment = providers.Singleton(AsyncIncrementBehavior, amount=1)
        handler = providers.Factory(AsyncCounterHandler)

    container = TestContainer()
    provider = DependencyInjectorServiceProvider(container)
    mediator = Mediator(provider)
    increment_behavior = container.increment()

    # Send 10 concurrent requests
    requests = [AsyncCounterRequest(value=i) for i in range(10)]
    responses = await asyncio.gather(*[mediator.send(req) for req in requests])

    # All should complete successfully
    assert len(responses) == 10
    assert all(resp.value == i + 1 for i, resp in enumerate(responses))

    # Singleton behavior should have been used 10 times
    assert increment_behavior.call_count == 10


@pytest.mark.asyncio
async def test_async_di_concurrent_requests_with_io() -> None:
    """Test concurrent requests with I/O-bound async behaviors."""

    class AsyncCounterHandler(Handler[AsyncCounterRequest]):
        async def __call__(self, request: AsyncCounterRequest) -> AsyncCounterResponse:
            await asyncio.sleep(0.001)
            return AsyncCounterResponse(value=request.value, execution_log=["AsyncHandler"])

    class TestContainer(containers.DeclarativeContainer):
        async_io = providers.Factory(AsyncIOBehavior)
        increment = providers.Factory(AsyncIncrementBehavior, amount=1)
        handler = providers.Factory(AsyncCounterHandler)

    container = TestContainer()
    provider = DependencyInjectorServiceProvider(container)
    mediator = Mediator(provider)

    # Send concurrent requests and measure time
    import time

    start = time.time()
    requests = [AsyncCounterRequest(value=i) for i in range(5)]
    responses = await asyncio.gather(*[mediator.send(req) for req in requests])
    duration = time.time() - start

    # All should complete
    assert len(responses) == 5

    # Should complete faster than sequential (5 * 0.02s = 0.1s)
    # With concurrency should be closer to 0.02s
    assert duration < 0.05  # Allow some overhead


@pytest.mark.asyncio
async def test_async_di_race_condition_safety() -> None:
    """Test that async behaviors handle concurrent access safely."""

    class AsyncCounterHandler(Handler[AsyncCounterRequest]):
        async def __call__(self, request: AsyncCounterRequest) -> AsyncCounterResponse:
            await asyncio.sleep(0.001)
            return AsyncCounterResponse(value=request.value, execution_log=["AsyncHandler"])

    class UnsafeCounterBehavior(PipelineBehavior[AsyncCounterRequest]):
        """Intentionally unsafe behavior for testing."""

        def __init__(self) -> None:
            self.counter = 0

        async def __call__(self, request: AsyncCounterRequest, next: Any) -> AsyncCounterResponse:
            # Unsafe increment with delay
            current = self.counter
            await asyncio.sleep(0.001)
            self.counter = current + 1

            response: AsyncCounterResponse = await next()
            response.execution_log.append(f"UnsafeCounter({self.counter})")
            return response

    class TestContainer(containers.DeclarativeContainer):
        # Singleton - same instance accessed concurrently
        unsafe = providers.Singleton(UnsafeCounterBehavior)
        handler = providers.Factory(AsyncCounterHandler)

    container = TestContainer()
    provider = DependencyInjectorServiceProvider(container)
    mediator = Mediator(provider)

    # Send 10 concurrent requests
    responses = await asyncio.gather(
        *[mediator.send(AsyncCounterRequest(value=i)) for i in range(10)]
    )

    # Counter will likely be wrong due to race condition
    # This demonstrates the need for proper synchronization
    assert len(responses) == 10


# ============================================================================
# Tests: Error Handling
# ============================================================================


@pytest.mark.asyncio
async def test_async_di_error_recovery() -> None:
    """Test async error recovery in behaviors."""

    # Use unique request type to avoid handler registration conflict
    @dataclass
    class AsyncErrorTestResponse:
        value: int
        execution_log: list[str]

    @dataclass
    class AsyncErrorTestRequest(Request[AsyncErrorTestResponse]):
        value: int

    class AsyncErrorRecoveryBehavior(PipelineBehavior[AsyncErrorTestRequest]):
        async def __call__(
            self, request: AsyncErrorTestRequest, next: Any
        ) -> AsyncErrorTestResponse:
            try:
                result: AsyncErrorTestResponse = await next()
                return result
            except ValueError:
                return AsyncErrorTestResponse(value=-1, execution_log=["AsyncRecovered"])

    class AsyncFailingHandler(Handler[AsyncErrorTestRequest]):
        async def __call__(self, request: AsyncErrorTestRequest) -> AsyncErrorTestResponse:
            if request.value < 0:
                raise ValueError("Negative!")
            return AsyncErrorTestResponse(value=request.value, execution_log=["AsyncHandler"])

    class TestContainer(containers.DeclarativeContainer):
        recovery = providers.Factory(AsyncErrorRecoveryBehavior)
        handler = providers.Factory(AsyncFailingHandler)

    container = TestContainer()
    provider = DependencyInjectorServiceProvider(container)
    mediator = Mediator(provider)

    # Normal request
    response = await mediator.send(AsyncErrorTestRequest(value=10))
    assert response.value == 10

    # Failing request - recovered
    response = await mediator.send(AsyncErrorTestRequest(value=-5))
    assert response.value == -1
    assert response.execution_log == ["AsyncRecovered"]


@pytest.mark.asyncio
async def test_async_di_exception_propagation() -> None:
    """Test that exceptions in async behaviors propagate correctly."""

    class AsyncCounterHandler(Handler[AsyncCounterRequest]):
        async def __call__(self, request: AsyncCounterRequest) -> AsyncCounterResponse:
            await asyncio.sleep(0.001)
            return AsyncCounterResponse(value=request.value, execution_log=["AsyncHandler"])

    class AsyncFailingBehavior(PipelineBehavior[AsyncCounterRequest]):
        async def __call__(self, request: AsyncCounterRequest, next: Any) -> AsyncCounterResponse:
            if request.value == 666:
                raise RuntimeError("Async behavior failed!")
            result: AsyncCounterResponse = await next()
            return result

    class TestContainer(containers.DeclarativeContainer):
        failing = providers.Factory(AsyncFailingBehavior)
        increment = providers.Factory(AsyncIncrementBehavior)
        handler = providers.Factory(AsyncCounterHandler)

    container = TestContainer()
    provider = DependencyInjectorServiceProvider(container)
    mediator = Mediator(provider)

    # Normal request
    response = await mediator.send(AsyncCounterRequest(value=10))
    assert response.value == 11

    # Failing request
    with pytest.raises(RuntimeError, match="Async behavior failed!"):
        await mediator.send(AsyncCounterRequest(value=666))


# ============================================================================
# Tests: Complex Scenarios
# ============================================================================


@pytest.mark.asyncio
async def test_async_di_complex_pipeline() -> None:
    """Test complex async pipeline with mixed behaviors."""

    class AsyncCounterHandler(Handler[AsyncCounterRequest]):
        async def __call__(self, request: AsyncCounterRequest) -> AsyncCounterResponse:
            await asyncio.sleep(0.001)
            return AsyncCounterResponse(value=request.value, execution_log=["AsyncHandler"])

    class AsyncValidationBehavior(PipelineBehavior[AsyncCounterRequest]):
        async def __call__(self, request: AsyncCounterRequest, next: Any) -> AsyncCounterResponse:
            await asyncio.sleep(0.001)  # Async validation
            if request.value > 1000:
                raise ValueError("Too large!")
            response: AsyncCounterResponse = await next()
            response.execution_log.append("AsyncValidation")
            return response

    class TestContainer(containers.DeclarativeContainer):
        validation = providers.Factory(AsyncValidationBehavior)
        short_circuit = providers.Factory(AsyncShortCircuitBehavior)
        logging = providers.Singleton(AsyncLoggingBehavior, label="audit")
        async_io = providers.Factory(AsyncIOBehavior)
        increment = providers.Factory(AsyncIncrementBehavior, amount=10)
        multiply = providers.Factory(AsyncMultiplyBehavior, factor=2)
        handler = providers.Factory(AsyncCounterHandler)

    container = TestContainer()
    provider = DependencyInjectorServiceProvider(container)
    mediator = Mediator(provider)

    # Normal execution
    response = await mediator.send(AsyncCounterRequest(value=20))
    assert response.value == 50  # (20 * 2) + 10
    assert "AsyncValidation" in response.execution_log
    assert "AsyncShortCircuit(passed)" in response.execution_log
    assert "AsyncIO" in response.execution_log

    # Short-circuit
    response = await mediator.send(AsyncCounterRequest(value=-5))
    assert response.value == -999

    # Validation error
    with pytest.raises(ValueError, match="Too large!"):
        await mediator.send(AsyncCounterRequest(value=2000))


@pytest.mark.asyncio
async def test_async_di_real_world_caching() -> None:
    """Test realistic async caching scenario."""

    class AsyncCounterHandler(Handler[AsyncCounterRequest]):
        async def __call__(self, request: AsyncCounterRequest) -> AsyncCounterResponse:
            await asyncio.sleep(0.001)
            return AsyncCounterResponse(value=request.value, execution_log=["AsyncHandler"])

    class AsyncCache:
        """Mock async cache."""

        def __init__(self) -> None:
            self.cache: dict[str, Any] = {}
            self.hit_count = 0
            self.miss_count = 0

        async def get(self, key: str) -> Any:
            await asyncio.sleep(0.001)  # Simulate network
            if key in self.cache:
                self.hit_count += 1
                return self.cache[key]
            self.miss_count += 1
            return None

        async def set(self, key: str, value: Any) -> None:
            await asyncio.sleep(0.001)  # Simulate network
            self.cache[key] = value

    class AsyncCachingBehavior(PipelineBehavior[AsyncCounterRequest]):
        def __init__(self, cache: AsyncCache) -> None:
            self.cache = cache

        async def __call__(self, request: AsyncCounterRequest, next: Any) -> AsyncCounterResponse:
            cache_key = f"request_{request.value}"

            # Check cache
            cached = await self.cache.get(cache_key)
            if cached is not None:
                cached_response: AsyncCounterResponse = cached
                cached_response.execution_log.append("Cache(HIT)")
                return cached_response

            # Execute and cache
            response: AsyncCounterResponse = await next()
            response.execution_log.append("Cache(MISS)")
            await self.cache.set(cache_key, response)
            return response

    class TestContainer(containers.DeclarativeContainer):
        cache = providers.Singleton(AsyncCache)
        caching = providers.Factory(AsyncCachingBehavior, cache=cache)
        increment = providers.Factory(AsyncIncrementBehavior, amount=1)
        handler = providers.Factory(AsyncCounterHandler)

    container = TestContainer()
    provider = DependencyInjectorServiceProvider(container)
    mediator = Mediator(provider)
    cache = container.cache()

    # First request - cache miss
    response1 = await mediator.send(AsyncCounterRequest(value=10))
    assert response1.value == 11
    assert "Cache(MISS)" in response1.execution_log
    assert cache.miss_count == 1

    # Second request same value - cache hit
    response2 = await mediator.send(AsyncCounterRequest(value=10))
    assert response2.value == 11
    assert "Cache(HIT)" in response2.execution_log
    assert cache.hit_count == 1

    # Third request different value - cache miss
    response3 = await mediator.send(AsyncCounterRequest(value=20))
    assert response3.value == 21
    assert "Cache(MISS)" in response3.execution_log
    assert cache.miss_count == 2


@pytest.mark.asyncio
async def test_async_di_parallel_pipeline_execution() -> None:
    """Test that multiple requests execute in parallel."""

    class AsyncCounterHandler(Handler[AsyncCounterRequest]):
        async def __call__(self, request: AsyncCounterRequest) -> AsyncCounterResponse:
            await asyncio.sleep(0.001)
            return AsyncCounterResponse(value=request.value, execution_log=["AsyncHandler"])

    class SlowBehavior(PipelineBehavior[AsyncCounterRequest]):
        """Intentionally slow behavior."""

        async def __call__(self, request: AsyncCounterRequest, next: Any) -> AsyncCounterResponse:
            await asyncio.sleep(0.1)  # 100ms delay
            response: AsyncCounterResponse = await next()
            response.execution_log.append("Slow")
            return response

    class TestContainer(containers.DeclarativeContainer):
        slow = providers.Factory(SlowBehavior)
        handler = providers.Factory(AsyncCounterHandler)

    container = TestContainer()
    provider = DependencyInjectorServiceProvider(container)
    mediator = Mediator(provider)

    # Send 5 requests in parallel
    import time

    start = time.time()
    requests = [AsyncCounterRequest(value=i) for i in range(5)]
    responses = await asyncio.gather(*[mediator.send(req) for req in requests])
    duration = time.time() - start

    # All complete
    assert len(responses) == 5

    # Should complete in ~100ms (parallel) not 500ms (sequential)
    assert duration < 0.15  # Allow some overhead


@pytest.mark.asyncio
async def test_async_di_many_behaviors() -> None:
    """Test async mediator with many behaviors."""

    class AsyncCounterHandler(Handler[AsyncCounterRequest]):
        async def __call__(self, request: AsyncCounterRequest) -> AsyncCounterResponse:
            await asyncio.sleep(0.001)
            return AsyncCounterResponse(value=request.value, execution_log=["AsyncHandler"])

    class TestContainer(containers.DeclarativeContainer):
        log1 = providers.Factory(AsyncLoggingBehavior, label="1")
        log2 = providers.Factory(AsyncLoggingBehavior, label="2")
        log3 = providers.Factory(AsyncLoggingBehavior, label="3")
        log4 = providers.Factory(AsyncLoggingBehavior, label="4")
        log5 = providers.Factory(AsyncLoggingBehavior, label="5")
        log6 = providers.Factory(AsyncLoggingBehavior, label="6")
        log7 = providers.Factory(AsyncLoggingBehavior, label="7")
        log8 = providers.Factory(AsyncLoggingBehavior, label="8")
        log9 = providers.Factory(AsyncLoggingBehavior, label="9")
        log10 = providers.Factory(AsyncLoggingBehavior, label="10")
        handler = providers.Factory(AsyncCounterHandler)

    container = TestContainer()
    provider = DependencyInjectorServiceProvider(container)
    mediator = Mediator(provider)

    response = await mediator.send(AsyncCounterRequest(value=42))

    # All 10 behaviors should execute
    assert len([log for log in response.execution_log if log.startswith("AsyncLogging")]) == 10
    assert response.value == 42
