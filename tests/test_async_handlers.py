"""Comprehensive test suite for async handlers with all resolver types."""

import asyncio
from dataclasses import dataclass, field
from typing import Any

import pytest

from pymediate import (
    DependencyInjectorResolver,
    Handler,
    HandlerNotFoundError,
    Mediator,
    Request,
    SimpleResolver,
)

# ============================================================================
# Test Requests and Responses (Dataclasses)
# ============================================================================


@dataclass
class FetchUserResponse:
    user_id: int
    username: str
    email: str


@dataclass
class FetchUserRequest(Request[FetchUserResponse]):
    user_id: int


@dataclass
class ProcessDataResponse:
    processed_items: list[str]
    total_processed: int
    duration_ms: float


@dataclass
class ProcessDataRequest(Request[ProcessDataResponse]):
    items: list[str]
    batch_size: int = 10


@dataclass
class ComputeResponse:
    result: int
    computation_time_ms: float


@dataclass
class ComputeRequest(Request[ComputeResponse]):
    a: int
    b: int
    operation: str  # "add", "multiply", "power"


@dataclass
class MultiStepResponse:
    step1_result: str
    step2_result: str
    step3_result: str
    total_time_ms: float


@dataclass
class MultiStepRequest(Request[MultiStepResponse]):
    input_data: str


@dataclass
class ErrorResponse:
    success: bool
    error_message: str | None = None


@dataclass
class ErrorRequest(Request[ErrorResponse]):
    should_fail: bool


@dataclass
class ParallelTaskResponse:
    task_results: list[int]
    total_time_ms: float


@dataclass
class ParallelTaskRequest(Request[ParallelTaskResponse]):
    task_count: int
    delay_ms: int = 10


@dataclass
class CachedDataResponse:
    data: dict[str, Any]
    from_cache: bool


@dataclass
class CachedDataRequest(Request[CachedDataResponse]):
    key: str


# ============================================================================
# Mock Async Services
# ============================================================================


class AsyncDatabaseService:
    """Mock async database service."""

    def __init__(self):
        self.users = {
            1: {"user_id": 1, "username": "alice", "email": "alice@example.com"},
            2: {"user_id": 2, "username": "bob", "email": "bob@example.com"},
            3: {"user_id": 3, "username": "charlie", "email": "charlie@example.com"},
        }
        self.fetch_count = 0

    async def fetch_user(self, user_id: int) -> dict[str, Any] | None:
        """Simulate async database fetch."""
        await asyncio.sleep(0.01)  # Simulate network delay
        self.fetch_count += 1
        return self.users.get(user_id)


class AsyncCacheService:
    """Mock async cache service."""

    def __init__(self):
        self.cache: dict[str, Any] = {}
        self.hits = 0
        self.misses = 0

    async def get(self, key: str) -> Any | None:
        """Get value from cache."""
        await asyncio.sleep(0.001)  # Simulate network delay
        if key in self.cache:
            self.hits += 1
            return self.cache[key]
        self.misses += 1
        return None

    async def set(self, key: str, value: Any, ttl: int = 60) -> None:
        """Set value in cache."""
        await asyncio.sleep(0.001)
        self.cache[key] = value


class AsyncComputeService:
    """Mock async compute service."""

    async def compute(self, a: int, b: int, operation: str) -> int:
        """Perform async computation."""
        await asyncio.sleep(0.005)  # Simulate computation time

        if operation == "add":
            return a + b
        elif operation == "multiply":
            return a * b
        elif operation == "power":
            return a**b
        else:
            raise ValueError(f"Unknown operation: {operation}")


# ============================================================================
# Async Handlers
# ============================================================================


class AsyncFetchUserHandler(Handler[FetchUserRequest]):
    """Async handler that fetches user from database."""

    def __init__(self, database: AsyncDatabaseService):
        self.database = database

    async def __call__(self, request: FetchUserRequest) -> FetchUserResponse:
        user = await self.database.fetch_user(request.user_id)

        if not user:
            raise ValueError(f"User {request.user_id} not found")

        return FetchUserResponse(
            user_id=user["user_id"],
            username=user["username"],
            email=user["email"],
        )


class AsyncProcessDataHandler(Handler[ProcessDataRequest]):
    """Async handler that processes data in batches."""

    async def __call__(self, request: ProcessDataRequest) -> ProcessDataResponse:
        import time

        start = time.time()
        processed = []

        # Process items in batches
        for i in range(0, len(request.items), request.batch_size):
            batch = request.items[i : i + request.batch_size]
            # Simulate async processing
            await asyncio.sleep(0.01)
            processed.extend([item.upper() for item in batch])

        duration_ms = (time.time() - start) * 1000

        return ProcessDataResponse(
            processed_items=processed,
            total_processed=len(processed),
            duration_ms=duration_ms,
        )


class AsyncComputeHandler(Handler[ComputeRequest]):
    """Async handler using external compute service."""

    def __init__(self, compute_service: AsyncComputeService):
        self.compute_service = compute_service

    async def __call__(self, request: ComputeRequest) -> ComputeResponse:
        import time

        start = time.time()

        result = await self.compute_service.compute(request.a, request.b, request.operation)

        duration_ms = (time.time() - start) * 1000

        return ComputeResponse(result=result, computation_time_ms=duration_ms)


class AsyncMultiStepHandler(Handler[MultiStepRequest]):
    """Async handler that performs multiple sequential async operations."""

    async def __call__(self, request: MultiStepRequest) -> MultiStepResponse:
        import time

        start = time.time()

        # Step 1: Process input
        await asyncio.sleep(0.01)
        step1 = f"Processed: {request.input_data}"

        # Step 2: Transform
        await asyncio.sleep(0.01)
        step2 = step1.upper()

        # Step 3: Finalize
        await asyncio.sleep(0.01)
        step3 = f"Final: {step2}"

        duration_ms = (time.time() - start) * 1000

        return MultiStepResponse(
            step1_result=step1,
            step2_result=step2,
            step3_result=step3,
            total_time_ms=duration_ms,
        )


class AsyncErrorHandler(Handler[ErrorRequest]):
    """Async handler that can simulate errors."""

    async def __call__(self, request: ErrorRequest) -> ErrorResponse:
        await asyncio.sleep(0.01)

        if request.should_fail:
            raise RuntimeError("Simulated async error")

        return ErrorResponse(success=True)


class AsyncParallelTaskHandler(Handler[ParallelTaskRequest]):
    """Async handler that executes tasks in parallel."""

    async def _run_task(self, task_id: int, delay_ms: int) -> int:
        """Simulate a single async task."""
        await asyncio.sleep(delay_ms / 1000)
        return task_id * 2

    async def __call__(self, request: ParallelTaskRequest) -> ParallelTaskResponse:
        import time

        start = time.time()

        # Run tasks in parallel using asyncio.gather
        tasks = [self._run_task(i, request.delay_ms) for i in range(request.task_count)]
        results = await asyncio.gather(*tasks)

        duration_ms = (time.time() - start) * 1000

        return ParallelTaskResponse(task_results=list(results), total_time_ms=duration_ms)


class AsyncCachedDataHandler(Handler[CachedDataRequest]):
    """Async handler with caching support."""

    def __init__(self, cache: AsyncCacheService, database: AsyncDatabaseService):
        self.cache = cache
        self.database = database

    async def __call__(self, request: CachedDataRequest) -> CachedDataResponse:
        # Try cache first
        cached_data = await self.cache.get(request.key)
        if cached_data:
            return CachedDataResponse(data=cached_data, from_cache=True)

        # Cache miss - fetch from "database"
        # For this test, we'll create mock data
        await asyncio.sleep(0.02)  # Simulate slow DB query
        data = {"key": request.key, "value": f"data_for_{request.key}"}

        # Store in cache
        await self.cache.set(request.key, data)

        return CachedDataResponse(data=data, from_cache=False)


# ============================================================================
# Tests with SimpleResolver
# ============================================================================


@pytest.mark.asyncio
async def test_simple_async_handler():
    """Test basic async handler with SimpleResolver."""
    database = AsyncDatabaseService()
    resolver = SimpleResolver()
    resolver.register(FetchUserRequest, AsyncFetchUserHandler(database))

    mediator = Mediator(resolver)

    # Fetch user asynchronously
    response = await mediator.send(FetchUserRequest(user_id=1))

    assert response.user_id == 1
    assert response.username == "alice"
    assert response.email == "alice@example.com"
    assert database.fetch_count == 1


@pytest.mark.asyncio
async def test_async_batch_processing():
    """Test async handler that processes data in batches."""
    resolver = SimpleResolver()
    resolver.register(ProcessDataRequest, AsyncProcessDataHandler())

    mediator = Mediator(resolver)

    items = [f"item{i}" for i in range(25)]
    response = await mediator.send(ProcessDataRequest(items=items, batch_size=10))

    assert response.total_processed == 25
    assert response.processed_items == [item.upper() for item in items]
    assert response.duration_ms > 0


@pytest.mark.asyncio
async def test_async_with_external_service():
    """Test async handler with external async service."""
    compute_service = AsyncComputeService()
    resolver = SimpleResolver()
    resolver.register(ComputeRequest, AsyncComputeHandler(compute_service))

    mediator = Mediator(resolver)

    # Test different operations
    add_response = await mediator.send(ComputeRequest(a=5, b=3, operation="add"))
    assert add_response.result == 8

    mult_response = await mediator.send(ComputeRequest(a=4, b=7, operation="multiply"))
    assert mult_response.result == 28

    power_response = await mediator.send(ComputeRequest(a=2, b=10, operation="power"))
    assert power_response.result == 1024


@pytest.mark.asyncio
async def test_async_multi_step_handler():
    """Test async handler with multiple sequential steps."""
    resolver = SimpleResolver()
    resolver.register(MultiStepRequest, AsyncMultiStepHandler())

    mediator = Mediator(resolver)

    response = await mediator.send(MultiStepRequest(input_data="test data"))

    assert "Processed: test data" in response.step1_result
    assert "TEST DATA" in response.step2_result
    assert "Final:" in response.step3_result
    assert response.total_time_ms > 0


@pytest.mark.asyncio
async def test_async_error_handling():
    """Test error handling in async handlers."""
    resolver = SimpleResolver()
    resolver.register(ErrorRequest, AsyncErrorHandler())

    mediator = Mediator(resolver)

    # Successful request
    success_response = await mediator.send(ErrorRequest(should_fail=False))
    assert success_response.success is True

    # Failing request
    with pytest.raises(RuntimeError, match="Simulated async error"):
        await mediator.send(ErrorRequest(should_fail=True))


@pytest.mark.asyncio
async def test_async_parallel_tasks():
    """Test async handler executing multiple tasks in parallel."""
    resolver = SimpleResolver()
    resolver.register(ParallelTaskRequest, AsyncParallelTaskHandler())

    mediator = Mediator(resolver)

    # Run 5 tasks in parallel
    response = await mediator.send(ParallelTaskRequest(task_count=5, delay_ms=10))

    assert len(response.task_results) == 5
    assert response.task_results == [0, 2, 4, 6, 8]  # task_id * 2

    # Verify tasks ran in parallel (should be ~10ms, not 50ms)
    assert response.total_time_ms < 30  # Allow some overhead


@pytest.mark.asyncio
async def test_async_caching():
    """Test async handler with caching."""
    cache = AsyncCacheService()
    database = AsyncDatabaseService()
    resolver = SimpleResolver()
    resolver.register(CachedDataRequest, AsyncCachedDataHandler(cache, database))

    mediator = Mediator(resolver)

    # First request - cache miss
    response1 = await mediator.send(CachedDataRequest(key="user:1"))
    assert response1.from_cache is False
    assert cache.misses == 1
    assert cache.hits == 0

    # Second request - cache hit
    response2 = await mediator.send(CachedDataRequest(key="user:1"))
    assert response2.from_cache is True
    assert response2.data == response1.data
    assert cache.hits == 1


@pytest.mark.asyncio
async def test_multiple_concurrent_requests():
    """Test sending multiple async requests concurrently."""
    database = AsyncDatabaseService()
    resolver = SimpleResolver()
    resolver.register(FetchUserRequest, AsyncFetchUserHandler(database))

    mediator = Mediator(resolver)

    # Send multiple requests concurrently
    tasks = [
        mediator.send(FetchUserRequest(user_id=1)),
        mediator.send(FetchUserRequest(user_id=2)),
        mediator.send(FetchUserRequest(user_id=3)),
    ]

    responses = await asyncio.gather(*tasks)

    assert len(responses) == 3
    assert responses[0].username == "alice"
    assert responses[1].username == "bob"
    assert responses[2].username == "charlie"
    assert database.fetch_count == 3


# ============================================================================
# Tests with DependencyInjectorResolver
# ============================================================================


@pytest.mark.asyncio
async def test_async_with_di_resolver():
    """Test async handlers with DI container."""
    from dependency_injector import containers, providers

    # Create container
    class Container(containers.DeclarativeContainer):
        database = providers.Singleton(AsyncDatabaseService)
        cache = providers.Singleton(AsyncCacheService)
        compute_service = providers.Singleton(AsyncComputeService)

        fetch_user_handler = providers.Factory(AsyncFetchUserHandler, database=database)
        cached_data_handler = providers.Factory(
            AsyncCachedDataHandler, cache=cache, database=database
        )
        compute_handler = providers.Factory(AsyncComputeHandler, compute_service=compute_service)

    container = Container()
    resolver = DependencyInjectorResolver(container)
    mediator = Mediator(resolver)

    # Test fetch user
    user_response = await mediator.send(FetchUserRequest(user_id=2))
    assert user_response.username == "bob"

    # Test compute
    compute_response = await mediator.send(ComputeRequest(a=10, b=5, operation="add"))
    assert compute_response.result == 15


@pytest.mark.asyncio
async def test_async_di_with_shared_services():
    """Test multiple async handlers sharing DI services."""
    from dependency_injector import containers, providers

    class Container(containers.DeclarativeContainer):
        database = providers.Singleton(AsyncDatabaseService)
        cache = providers.Singleton(AsyncCacheService)

        fetch_user_handler = providers.Factory(AsyncFetchUserHandler, database=database)
        cached_data_handler = providers.Factory(
            AsyncCachedDataHandler, cache=cache, database=database
        )

    container = Container()
    resolver = DependencyInjectorResolver(container)
    mediator = Mediator(resolver)

    # Both handlers share the same database instance
    await mediator.send(FetchUserRequest(user_id=1))
    await mediator.send(CachedDataRequest(key="test"))

    # Verify shared database instance
    db = container.database()
    assert db.fetch_count == 2  # Both handlers used same instance


# ============================================================================
# Tests with Frozen Dataclasses
# ============================================================================


@dataclass(frozen=True)
class FrozenDataResponse:
    result: str
    timestamp: float


@dataclass(frozen=True)
class FrozenDataRequest(Request[FrozenDataResponse]):
    input: str


class AsyncFrozenDataHandler(Handler[FrozenDataRequest]):
    """Handler for frozen dataclass requests."""

    async def __call__(self, request: FrozenDataRequest) -> FrozenDataResponse:
        import time

        await asyncio.sleep(0.01)
        return FrozenDataResponse(result=f"Processed: {request.input}", timestamp=time.time())


@pytest.mark.asyncio
async def test_async_frozen_dataclasses():
    """Test async handlers with frozen dataclasses."""
    resolver = SimpleResolver()
    resolver.register(FrozenDataRequest, AsyncFrozenDataHandler())

    mediator = Mediator(resolver)

    request = FrozenDataRequest(input="test data")

    # Verify request is frozen
    with pytest.raises(AttributeError):  # FrozenInstanceError is a subclass of AttributeError
        request.input = "modified"  # type: ignore

    response = await mediator.send(request)
    assert "Processed: test data" in response.result

    # Verify response is frozen
    with pytest.raises(AttributeError):  # FrozenInstanceError is a subclass of AttributeError
        response.result = "modified"  # type: ignore


# ============================================================================
# Tests with Nested Dataclasses
# ============================================================================


@dataclass
class Address:
    street: str
    city: str
    country: str


@dataclass
class UserProfile:
    name: str
    email: str
    address: Address


@dataclass
class ComplexUserResponse:
    profile: UserProfile
    metadata: dict[str, Any]


@dataclass
class ComplexUserRequest(Request[ComplexUserResponse]):
    user_id: int


class AsyncComplexUserHandler(Handler[ComplexUserRequest]):
    """Handler for nested dataclass responses."""

    async def __call__(self, request: ComplexUserRequest) -> ComplexUserResponse:
        await asyncio.sleep(0.01)

        profile = UserProfile(
            name="Alice Smith",
            email="alice@example.com",
            address=Address(street="123 Main St", city="Springfield", country="USA"),
        )

        return ComplexUserResponse(
            profile=profile, metadata={"user_id": request.user_id, "version": 1}
        )


@pytest.mark.asyncio
async def test_async_nested_dataclasses():
    """Test async handlers with nested dataclasses."""
    resolver = SimpleResolver()
    resolver.register(ComplexUserRequest, AsyncComplexUserHandler())

    mediator = Mediator(resolver)

    response = await mediator.send(ComplexUserRequest(user_id=123))

    assert response.profile.name == "Alice Smith"
    assert response.profile.address.city == "Springfield"
    assert response.metadata["user_id"] == 123


# ============================================================================
# Tests with Default Values and Field Factories
# ============================================================================


@dataclass
class ConfigurableResponse:
    items: list[str]
    count: int


@dataclass
class ConfigurableRequest(Request[ConfigurableResponse]):
    query: str
    limit: int = 10
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class AsyncConfigurableHandler(Handler[ConfigurableRequest]):
    """Handler for request with defaults and factories."""

    async def __call__(self, request: ConfigurableRequest) -> ConfigurableResponse:
        await asyncio.sleep(0.01)
        items = [f"{request.query}_{i}" for i in range(request.limit)]
        return ConfigurableResponse(items=items, count=len(items))


@pytest.mark.asyncio
async def test_async_with_defaults_and_factories():
    """Test async handlers with dataclass defaults and field factories."""
    resolver = SimpleResolver()
    resolver.register(ConfigurableRequest, AsyncConfigurableHandler())

    mediator = Mediator(resolver)

    # Test with defaults
    response1 = await mediator.send(ConfigurableRequest(query="test"))
    assert len(response1.items) == 10

    # Test with custom values
    response2 = await mediator.send(
        ConfigurableRequest(
            query="search", limit=5, tags=["tag1", "tag2"], metadata={"key": "value"}
        )
    )
    assert len(response2.items) == 5


# ============================================================================
# Integration Tests
# ============================================================================


@pytest.mark.asyncio
async def test_mixed_sync_and_async_handlers():
    """Test mediator with both sync and async handlers."""

    @dataclass
    class SyncResponse:
        result: str

    @dataclass
    class SyncRequest(Request[SyncResponse]):
        input: str

    class SyncHandler(Handler[SyncRequest]):
        def __call__(self, request: SyncRequest) -> SyncResponse:
            return SyncResponse(result=f"Sync: {request.input}")

    # Setup both sync and async handlers
    resolver = SimpleResolver()
    resolver.register(SyncRequest, SyncHandler())
    resolver.register(FetchUserRequest, AsyncFetchUserHandler(AsyncDatabaseService()))

    mediator = Mediator(resolver)

    # Sync handler - called normally
    sync_response = mediator.send(SyncRequest(input="test"))
    assert sync_response.result == "Sync: test"

    # Async handler - must be awaited
    async_response = await mediator.send(FetchUserRequest(user_id=1))
    assert async_response.username == "alice"


@pytest.mark.asyncio
async def test_async_handler_not_found():
    """Test HandlerNotFoundError with async requests."""
    resolver = SimpleResolver()
    mediator = Mediator(resolver)

    with pytest.raises(HandlerNotFoundError) as exc_info:
        await mediator.send(FetchUserRequest(user_id=1))

    assert exc_info.value.request_type == FetchUserRequest


@pytest.mark.asyncio
async def test_async_performance():
    """Test that parallel async operations are actually concurrent."""
    import time

    resolver = SimpleResolver()
    resolver.register(ParallelTaskRequest, AsyncParallelTaskHandler())

    mediator = Mediator(resolver)

    start = time.time()

    # Run 10 tasks, each taking 20ms
    # If sequential: ~200ms
    # If parallel: ~20ms
    response = await mediator.send(ParallelTaskRequest(task_count=10, delay_ms=20))

    elapsed_ms = (time.time() - start) * 1000

    # Should complete in roughly the time of one task, not all tasks
    assert elapsed_ms < 50  # Allow overhead, but much less than 200ms
    assert len(response.task_results) == 10


@pytest.mark.asyncio
async def test_complex_async_workflow():
    """Test complex workflow with multiple async handlers."""
    from dependency_injector import containers, providers

    class Container(containers.DeclarativeContainer):
        database = providers.Singleton(AsyncDatabaseService)
        cache = providers.Singleton(AsyncCacheService)
        compute_service = providers.Singleton(AsyncComputeService)

        fetch_user_handler = providers.Factory(AsyncFetchUserHandler, database=database)
        compute_handler = providers.Factory(AsyncComputeHandler, compute_service=compute_service)
        process_data_handler = providers.Factory(AsyncProcessDataHandler)

    container = Container()
    resolver = DependencyInjectorResolver(container)
    mediator = Mediator(resolver)

    # Complex workflow: fetch user, compute, process data
    user_response = await mediator.send(FetchUserRequest(user_id=1))
    assert user_response.username == "alice"

    compute_response = await mediator.send(
        ComputeRequest(a=user_response.user_id, b=10, operation="multiply")
    )
    assert compute_response.result == 10

    process_response = await mediator.send(ProcessDataRequest(items=["a", "b", "c"], batch_size=2))
    assert process_response.processed_items == ["A", "B", "C"]


@pytest.mark.asyncio
async def test_async_handler_validation():
    """Test validation in async request dataclasses."""

    @dataclass
    class ValidatedResponse:
        success: bool

    @dataclass
    class ValidatedRequest(Request[ValidatedResponse]):
        email: str
        age: int

        def __post_init__(self):
            if "@" not in self.email:
                raise ValueError("Invalid email format")
            if self.age < 18:
                raise ValueError("Must be 18 or older")

    class AsyncValidatedHandler(Handler[ValidatedRequest]):
        async def __call__(self, request: ValidatedRequest) -> ValidatedResponse:
            await asyncio.sleep(0.01)
            return ValidatedResponse(success=True)

    resolver = SimpleResolver()
    resolver.register(ValidatedRequest, AsyncValidatedHandler())
    mediator = Mediator(resolver)

    # Valid request
    response = await mediator.send(ValidatedRequest(email="test@example.com", age=25))
    assert response.success is True

    # Invalid email
    with pytest.raises(ValueError, match="Invalid email"):
        ValidatedRequest(email="invalid", age=25)

    # Invalid age
    with pytest.raises(ValueError, match="Must be 18"):
        ValidatedRequest(email="test@example.com", age=16)
