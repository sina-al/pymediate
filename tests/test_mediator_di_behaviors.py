"""Comprehensive DI container tests for mediator with pipeline behaviors.

This mega test suite covers all edge cases for pipeline behaviors when using
DependencyInjectorServiceProvider with the mediator.


"""

from dataclasses import dataclass
from typing import Any

import pytest
from dependency_injector import containers, providers

from pymediate.providers import DependencyInjectorServiceProvider
from pymediate.sync import (
    InvalidPipelineBehaviorsError,
    Mediator,
    PipelineBehavior,
    Request,
    RequestHandler,
    ServiceNotFoundError,
)

# ============================================================================
# Test Fixtures - Requests and Responses
# ============================================================================


@dataclass
class CounterResponse:
    """Response that tracks execution count and value transformations."""

    value: int
    execution_log: list[str]


@dataclass
class CounterRequest(Request[CounterResponse]):
    """Request with a value to transform."""

    value: int


@dataclass
class SimpleResponse:
    """Simple response."""

    message: str


@dataclass
class SimpleRequest(Request[SimpleResponse]):
    """Simple request."""

    data: str


# ============================================================================
# Test Fixtures - Basic Behaviors
# ============================================================================


class IncrementBehavior(PipelineBehavior[CounterRequest]):
    """Increments the value by a configured amount."""

    def __init__(self, amount: int = 1) -> None:
        self.amount = amount
        self.call_count = 0

    def __call__(self, request: CounterRequest, next: Any) -> CounterResponse:
        self.call_count += 1
        response: CounterResponse = next()
        response.value += self.amount
        response.execution_log.append(f"Increment(+{self.amount})")
        return response


class MultiplyBehavior(PipelineBehavior[CounterRequest]):
    """Multiplies the value by a configured amount."""

    def __init__(self, factor: int = 2) -> None:
        self.factor = factor
        self.call_count = 0

    def __call__(self, request: CounterRequest, next: Any) -> CounterResponse:
        self.call_count += 1
        response: CounterResponse = next()
        response.value *= self.factor
        response.execution_log.append(f"Multiply(*{self.factor})")
        return response


class LoggingBehavior(PipelineBehavior[CounterRequest]):
    """Logs execution with a label."""

    def __init__(self, label: str = "default") -> None:
        self.label = label
        self.call_count = 0

    def __call__(self, request: CounterRequest, next: Any) -> CounterResponse:
        self.call_count += 1
        response: CounterResponse = next()
        response.execution_log.append(f"Logging({self.label})")
        return response


# ============================================================================
# Test Fixtures - Short-Circuit Behaviors
# ============================================================================


class ShortCircuitBehavior(PipelineBehavior[CounterRequest]):
    """Short-circuits if request value is negative."""

    def __init__(self) -> None:
        self.call_count = 0
        self.short_circuited = False

    def __call__(self, request: CounterRequest, next: Any) -> CounterResponse:
        self.call_count += 1
        if request.value < 0:
            self.short_circuited = True
            return CounterResponse(value=-999, execution_log=["ShortCircuit"])
        response: CounterResponse = next()
        response.execution_log.append("ShortCircuit(passed)")
        return response


class ConditionalBehavior(PipelineBehavior[CounterRequest]):
    """Only executes modification if condition is met."""

    def __init__(self, threshold: int) -> None:
        self.threshold = threshold
        self.call_count = 0

    def __call__(self, request: CounterRequest, next: Any) -> CounterResponse:
        self.call_count += 1
        response: CounterResponse = next()
        if request.value >= self.threshold:
            response.value += 100
            response.execution_log.append(f"Conditional(>={self.threshold}:+100)")
        else:
            response.execution_log.append(f"Conditional(<{self.threshold}:skip)")
        return response


# ============================================================================
# Test Fixtures - Behavior Inheritance
# ============================================================================


class BaseBehavior(PipelineBehavior[CounterRequest]):
    """Base behavior for testing inheritance."""

    def __init__(self, tag: str) -> None:
        self.tag = tag
        self.call_count = 0

    def __call__(self, request: CounterRequest, next: Any) -> CounterResponse:
        self.call_count += 1
        response: CounterResponse = next()
        response.execution_log.append(f"Base({self.tag})")
        return response


class DerivedBehaviorA(BaseBehavior):
    """Derived behavior A."""

    def __init__(self) -> None:
        super().__init__("DerivedA")


class DerivedBehaviorB(BaseBehavior):
    """Derived behavior B."""

    def __init__(self) -> None:
        super().__init__("DerivedB")


# ============================================================================
# Test Fixtures - Behavior Mixins
# ============================================================================


class AuditMixin:
    """Mixin that adds audit logging."""

    def audit(self, message: str, log: list[str]) -> None:
        log.append(f"[AUDIT:{type(self).__name__}] {message}")


class MetricsMixin:
    """Mixin that adds metrics tracking."""

    def record_metric(self, metric: str, log: list[str]) -> None:
        log.append(f"[METRIC:{type(self).__name__}] {metric}")


class AuditedBehavior(AuditMixin, PipelineBehavior[CounterRequest]):
    """Behavior with audit mixin."""

    def __call__(self, request: CounterRequest, next: Any) -> CounterResponse:
        response: CounterResponse = next()
        self.audit("executed", response.execution_log)
        return response


class MetricsBehavior(MetricsMixin, PipelineBehavior[CounterRequest]):
    """Behavior with metrics mixin."""

    def __call__(self, request: CounterRequest, next: Any) -> CounterResponse:
        response: CounterResponse = next()
        self.record_metric("processed", response.execution_log)
        return response


class CombinedMixinBehavior(AuditMixin, MetricsMixin, PipelineBehavior[CounterRequest]):
    """Behavior with multiple mixins."""

    def __call__(self, request: CounterRequest, next: Any) -> CounterResponse:
        response: CounterResponse = next()
        self.audit("started", response.execution_log)
        self.record_metric("count", response.execution_log)
        return response


# ============================================================================
# Test Fixtures - Stateful Behaviors
# ============================================================================


class CountingBehavior(PipelineBehavior[CounterRequest]):
    """Tracks how many times it's been executed."""

    instance_counter = 0

    def __init__(self) -> None:
        CountingBehavior.instance_counter += 1
        self.instance_id = CountingBehavior.instance_counter
        self.execution_count = 0

    def __call__(self, request: CounterRequest, next: Any) -> CounterResponse:
        self.execution_count += 1
        response: CounterResponse = next()
        response.execution_log.append(
            f"Counting(inst={self.instance_id},exec={self.execution_count})"
        )
        return response


# ============================================================================
# Test Fixtures - Behaviors with Dependencies
# ============================================================================


class Database:
    """Mock database."""

    def __init__(self) -> None:
        self.query_count = 0

    def log_request(self, request_type: str) -> str:
        self.query_count += 1
        return f"Logged {request_type} (total: {self.query_count})"


class DatabaseLoggingBehavior(PipelineBehavior[CounterRequest]):
    """Behavior that depends on a database."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def __call__(self, request: CounterRequest, next: Any) -> CounterResponse:
        log_result = self.database.log_request("CounterRequest")
        response: CounterResponse = next()
        response.execution_log.append(f"DBLog({log_result})")
        return response


# ============================================================================
# Tests: Basic Behavior Execution
# ============================================================================


def test_di_mediator_with_single_behavior() -> None:
    """Test mediator with single behavior from DI container."""

    class CounterHandler(RequestHandler[CounterRequest]):
        def __call__(self, request: CounterRequest) -> CounterResponse:
            return CounterResponse(value=request.value, execution_log=["RequestHandler"])

    class TestContainer(containers.DeclarativeContainer):
        increment = providers.Factory(IncrementBehavior, amount=5)
        handler = providers.Factory(CounterHandler)

    container = TestContainer()
    provider = DependencyInjectorServiceProvider(container)
    mediator = Mediator(provider, behaviors=[IncrementBehavior])

    response = mediator.send(CounterRequest(value=10))

    assert response.value == 15  # 10 + 5
    assert "RequestHandler" in response.execution_log
    assert "Increment(+5)" in response.execution_log


def test_di_mediator_with_multiple_behaviors() -> None:
    """Test mediator with multiple behaviors from DI container."""

    class CounterHandler(RequestHandler[CounterRequest]):
        def __call__(self, request: CounterRequest) -> CounterResponse:
            return CounterResponse(value=request.value, execution_log=["RequestHandler"])

    class TestContainer(containers.DeclarativeContainer):
        increment = providers.Factory(IncrementBehavior, amount=3)
        multiply = providers.Factory(MultiplyBehavior, factor=2)
        logging = providers.Factory(LoggingBehavior, label="test")
        handler = providers.Factory(CounterHandler)

    container = TestContainer()
    provider = DependencyInjectorServiceProvider(container)
    mediator = Mediator(provider, behaviors=[IncrementBehavior, MultiplyBehavior, LoggingBehavior])

    response = mediator.send(CounterRequest(value=10))

    # Execution: handler(10) -> *2 = 20 -> +3 = 23
    assert response.value == 23
    assert response.execution_log == [
        "RequestHandler",
        "Logging(test)",
        "Multiply(*2)",
        "Increment(+3)",
    ]


def test_di_mediator_without_behaviors() -> None:
    """Test mediator with only handler (fast path)."""

    class CounterHandler(RequestHandler[CounterRequest]):
        def __call__(self, request: CounterRequest) -> CounterResponse:
            return CounterResponse(value=request.value, execution_log=["RequestHandler"])

    class TestContainer(containers.DeclarativeContainer):
        handler = providers.Factory(CounterHandler)

    container = TestContainer()
    provider = DependencyInjectorServiceProvider(container)
    mediator = Mediator(provider)

    response = mediator.send(CounterRequest(value=42))

    assert response.value == 42
    assert response.execution_log == ["RequestHandler"]


# ============================================================================
# Tests: Short-Circuit Behaviors
# ============================================================================


def test_di_short_circuit_behavior() -> None:
    """Test behavior that short-circuits based on condition."""

    class CounterHandler(RequestHandler[CounterRequest]):
        def __call__(self, request: CounterRequest) -> CounterResponse:
            return CounterResponse(value=request.value, execution_log=["RequestHandler"])

    class TestContainer(containers.DeclarativeContainer):
        short_circuit = providers.Factory(ShortCircuitBehavior)
        increment = providers.Factory(IncrementBehavior, amount=10)
        handler = providers.Factory(CounterHandler)

    container = TestContainer()
    provider = DependencyInjectorServiceProvider(container)
    mediator = Mediator(provider, behaviors=[ShortCircuitBehavior, IncrementBehavior])

    # Positive value - no short circuit
    response = mediator.send(CounterRequest(value=5))
    assert response.value == 15  # 5 + 10
    assert "ShortCircuit(passed)" in response.execution_log
    assert "Increment(+10)" in response.execution_log

    # Negative value - short circuit
    response = mediator.send(CounterRequest(value=-5))
    assert response.value == -999
    assert response.execution_log == ["ShortCircuit"]


def test_di_conditional_behavior() -> None:
    """Test behavior with conditional logic."""

    class CounterHandler(RequestHandler[CounterRequest]):
        def __call__(self, request: CounterRequest) -> CounterResponse:
            return CounterResponse(value=request.value, execution_log=["RequestHandler"])

    class TestContainer(containers.DeclarativeContainer):
        conditional = providers.Factory(ConditionalBehavior, threshold=50)
        increment = providers.Factory(IncrementBehavior, amount=1)
        handler = providers.Factory(CounterHandler)

    container = TestContainer()
    provider = DependencyInjectorServiceProvider(container)
    mediator = Mediator(provider, behaviors=[ConditionalBehavior, IncrementBehavior])

    # Below threshold
    response = mediator.send(CounterRequest(value=10))
    assert response.value == 11  # 10 + 1, condition not met
    assert "Conditional(<50:skip)" in response.execution_log

    # Above threshold
    response = mediator.send(CounterRequest(value=100))
    assert response.value == 201  # 100 + 1 + 100 (conditional bonus)
    assert "Conditional(>=50:+100)" in response.execution_log


# ============================================================================
# Tests: Registration Order
# ============================================================================


def test_di_behaviors_order_follows_behaviors_list_not_registration() -> None:
    """Test that the behaviors= list, not container declaration order, determines order."""

    class CounterHandler(RequestHandler[CounterRequest]):
        def __call__(self, request: CounterRequest) -> CounterResponse:
            return CounterResponse(value=request.value, execution_log=["RequestHandler"])

    # Both containers declare increment then multiply; only the behaviors= list differs.
    class Container1(containers.DeclarativeContainer):
        increment = providers.Factory(IncrementBehavior, amount=5)
        multiply = providers.Factory(MultiplyBehavior, factor=2)
        handler = providers.Factory(CounterHandler)

    class Container2(containers.DeclarativeContainer):
        increment = providers.Factory(IncrementBehavior, amount=5)
        multiply = providers.Factory(MultiplyBehavior, factor=2)
        handler = providers.Factory(CounterHandler)

    mediator1 = Mediator(
        DependencyInjectorServiceProvider(Container1()),
        behaviors=[IncrementBehavior, MultiplyBehavior],
    )
    mediator2 = Mediator(
        DependencyInjectorServiceProvider(Container2()),
        behaviors=[MultiplyBehavior, IncrementBehavior],
    )

    response1 = mediator1.send(CounterRequest(value=10))
    response2 = mediator2.send(CounterRequest(value=10))

    # mediator1: Increment outermost -> Multiply innermost: 10 * 2 = 20, then + 5 = 25
    assert response1.value == 25
    assert response1.execution_log == ["RequestHandler", "Multiply(*2)", "Increment(+5)"]

    # mediator2: Multiply outermost -> Increment innermost: (10 + 5) * 2 = 30
    assert response2.value == 30
    assert response2.execution_log == ["RequestHandler", "Increment(+5)", "Multiply(*2)"]


def test_di_complex_behaviors_list_order() -> None:
    """Test that the behaviors= list order drives a complex multi-behavior chain."""

    class CounterHandler(RequestHandler[CounterRequest]):
        def __call__(self, request: CounterRequest) -> CounterResponse:
            return CounterResponse(value=request.value, execution_log=["RequestHandler"])

    class TestContainer(containers.DeclarativeContainer):
        # Container declaration order is now cosmetic - the behaviors= list below is
        # what determines the pipeline order.
        log1 = providers.Factory(LoggingBehavior, label="first")
        increment = providers.Factory(IncrementBehavior, amount=2)
        log2 = providers.Factory(LoggingBehavior, label="second")
        multiply = providers.Factory(MultiplyBehavior, factor=3)
        log3 = providers.Factory(LoggingBehavior, label="third")
        handler = providers.Factory(CounterHandler)

    container = TestContainer()
    provider = DependencyInjectorServiceProvider(container)
    mediator = Mediator(
        provider,
        behaviors=[
            LoggingBehavior,
            IncrementBehavior,
            MultiplyBehavior,
        ],
    )

    response = mediator.send(CounterRequest(value=10))

    # Value: 10 * 3 = 30, + 2 = 32
    assert response.value == 32

    # Log order follows the behaviors= list (outermost first, unwinding inward). Which
    # of the three LoggingBehavior instances resolves for the single LoggingBehavior
    # entry is unspecified, so match only the concern, not the label.
    assert response.execution_log[:3] == ["RequestHandler", "Multiply(*3)", "Increment(+2)"]
    assert response.execution_log[3].startswith("Logging(")


# ============================================================================
# Tests: Nested Containers
# ============================================================================


def test_di_nested_containers() -> None:
    """Test behaviors from nested DI containers."""

    class CounterHandler(RequestHandler[CounterRequest]):
        def __call__(self, request: CounterRequest) -> CounterResponse:
            return CounterResponse(value=request.value, execution_log=["RequestHandler"])

    class CoreContainer(containers.DeclarativeContainer):
        """Core behaviors used across application."""

        logging = providers.Singleton(LoggingBehavior, label="core")

    class FeatureContainer(containers.DeclarativeContainer):
        """Feature-specific behaviors."""

        increment = providers.Factory(IncrementBehavior, amount=7)

    class AppContainer(containers.DeclarativeContainer):
        """Main application container."""

        core = providers.Container(CoreContainer)
        feature = providers.Container(FeatureContainer)
        handler = providers.Factory(CounterHandler)

    container = AppContainer()
    # Need to wire the containers to make providers visible
    container.core()
    container.feature()

    provider = DependencyInjectorServiceProvider(container)
    mediator = Mediator(provider, behaviors=[LoggingBehavior, IncrementBehavior])

    response = mediator.send(CounterRequest(value=10))

    assert response.value == 17
    assert response.execution_log == [
        "RequestHandler",
        "Increment(+7)",
        "Logging(core)",
    ]


def test_di_flat_container_composition() -> None:
    """Test composing behaviors from multiple containers into one flat container."""

    class CounterHandler(RequestHandler[CounterRequest]):
        def __call__(self, request: CounterRequest) -> CounterResponse:
            return CounterResponse(value=request.value, execution_log=["RequestHandler"])

    class CoreBehaviors(containers.DeclarativeContainer):
        logging = providers.Factory(LoggingBehavior, label="core")

    class FeatureBehaviors(containers.DeclarativeContainer):
        increment = providers.Factory(IncrementBehavior, amount=5)
        multiply = providers.Factory(MultiplyBehavior, factor=2)

    class AppContainer(containers.DeclarativeContainer):
        # Import behaviors from other containers
        core_logging = providers.Factory(LoggingBehavior, label="core")
        feature_increment = providers.Factory(IncrementBehavior, amount=5)
        feature_multiply = providers.Factory(MultiplyBehavior, factor=2)
        handler = providers.Factory(CounterHandler)

    container = AppContainer()
    provider = DependencyInjectorServiceProvider(container)
    mediator = Mediator(
        provider,
        behaviors=[LoggingBehavior, IncrementBehavior, MultiplyBehavior],
    )

    response = mediator.send(CounterRequest(value=10))

    # All behaviors should execute
    assert response.value == 25  # (10 * 2) + 5
    assert "Logging(core)" in response.execution_log
    assert "Increment(+5)" in response.execution_log
    assert "Multiply(*2)" in response.execution_log


# ============================================================================
# Tests: Behavior Inheritance
# ============================================================================


def test_di_behavior_inheritance() -> None:
    """Test that behavior subclasses are resolved correctly."""

    class CounterHandler(RequestHandler[CounterRequest]):
        def __call__(self, request: CounterRequest) -> CounterResponse:
            return CounterResponse(value=request.value, execution_log=["RequestHandler"])

    class TestContainer(containers.DeclarativeContainer):
        base = providers.Factory(BaseBehavior, tag="base")
        derived_a = providers.Factory(DerivedBehaviorA)
        derived_b = providers.Factory(DerivedBehaviorB)
        handler = providers.Factory(CounterHandler)

    container = TestContainer()
    provider = DependencyInjectorServiceProvider(container)
    mediator = Mediator(
        provider,
        behaviors=[BaseBehavior, DerivedBehaviorA, DerivedBehaviorB],
    )

    response = mediator.send(CounterRequest(value=10))

    # All three behaviors should execute
    assert "Base(base)" in response.execution_log
    assert "Base(DerivedA)" in response.execution_log
    assert "Base(DerivedB)" in response.execution_log


def test_di_behavior_polymorphism() -> None:
    """Test that behavior subclasses are each resolvable by their exact type."""

    class CounterHandler(RequestHandler[CounterRequest]):
        def __call__(self, request: CounterRequest) -> CounterResponse:
            return CounterResponse(value=request.value, execution_log=["RequestHandler"])

    class TestContainer(containers.DeclarativeContainer):
        behavior1 = providers.Factory(BaseBehavior, tag="1")
        behavior2 = providers.Factory(DerivedBehaviorA)
        behavior3 = providers.Factory(DerivedBehaviorB)
        handler = providers.Factory(CounterHandler)

    container = TestContainer()
    provider = DependencyInjectorServiceProvider(container)

    # Each behavior resolves by its exact type as a PipelineBehavior instance.
    for behavior_type in (BaseBehavior, DerivedBehaviorA, DerivedBehaviorB):
        assert isinstance(provider.get(behavior_type), PipelineBehavior)


# ============================================================================
# Tests: Behavior Mixins
# ============================================================================


def test_di_behavior_with_audit_mixin() -> None:
    """Test behavior with audit mixin."""

    class CounterHandler(RequestHandler[CounterRequest]):
        def __call__(self, request: CounterRequest) -> CounterResponse:
            return CounterResponse(value=request.value, execution_log=["RequestHandler"])

    class TestContainer(containers.DeclarativeContainer):
        audited = providers.Factory(AuditedBehavior)
        increment = providers.Factory(IncrementBehavior, amount=1)
        handler = providers.Factory(CounterHandler)

    container = TestContainer()
    provider = DependencyInjectorServiceProvider(container)
    mediator = Mediator(provider, behaviors=[AuditedBehavior, IncrementBehavior])

    response = mediator.send(CounterRequest(value=10))

    assert "[AUDIT:AuditedBehavior] executed" in response.execution_log


def test_di_behavior_with_metrics_mixin() -> None:
    """Test behavior with metrics mixin."""

    class CounterHandler(RequestHandler[CounterRequest]):
        def __call__(self, request: CounterRequest) -> CounterResponse:
            return CounterResponse(value=request.value, execution_log=["RequestHandler"])

    class TestContainer(containers.DeclarativeContainer):
        metrics = providers.Factory(MetricsBehavior)
        increment = providers.Factory(IncrementBehavior, amount=1)
        handler = providers.Factory(CounterHandler)

    container = TestContainer()
    provider = DependencyInjectorServiceProvider(container)
    mediator = Mediator(provider, behaviors=[MetricsBehavior, IncrementBehavior])

    response = mediator.send(CounterRequest(value=10))

    assert "[METRIC:MetricsBehavior] processed" in response.execution_log


def test_di_behavior_with_multiple_mixins() -> None:
    """Test behavior with multiple mixins."""

    class CounterHandler(RequestHandler[CounterRequest]):
        def __call__(self, request: CounterRequest) -> CounterResponse:
            return CounterResponse(value=request.value, execution_log=["RequestHandler"])

    class TestContainer(containers.DeclarativeContainer):
        combined = providers.Factory(CombinedMixinBehavior)
        handler = providers.Factory(CounterHandler)

    container = TestContainer()
    provider = DependencyInjectorServiceProvider(container)
    mediator = Mediator(provider, behaviors=[CombinedMixinBehavior])

    response = mediator.send(CounterRequest(value=10))

    assert "[AUDIT:CombinedMixinBehavior] started" in response.execution_log
    assert "[METRIC:CombinedMixinBehavior] count" in response.execution_log


def test_di_combination_of_behaviors_with_and_without_mixins() -> None:
    """Test mixture of behaviors with and without mixins."""

    class CounterHandler(RequestHandler[CounterRequest]):
        def __call__(self, request: CounterRequest) -> CounterResponse:
            return CounterResponse(value=request.value, execution_log=["RequestHandler"])

    class TestContainer(containers.DeclarativeContainer):
        # Regular behaviors
        increment = providers.Factory(IncrementBehavior, amount=5)
        multiply = providers.Factory(MultiplyBehavior, factor=2)
        # Mixin behaviors
        audited = providers.Factory(AuditedBehavior)
        metrics = providers.Factory(MetricsBehavior)
        combined = providers.Factory(CombinedMixinBehavior)
        handler = providers.Factory(CounterHandler)

    container = TestContainer()
    provider = DependencyInjectorServiceProvider(container)
    mediator = Mediator(
        provider,
        behaviors=[
            IncrementBehavior,
            MultiplyBehavior,
            AuditedBehavior,
            MetricsBehavior,
            CombinedMixinBehavior,
        ],
    )

    response = mediator.send(CounterRequest(value=10))

    # Value transformations from regular behaviors
    assert response.value == 25  # (10 * 2) + 5

    # Regular behaviors executed
    assert "Increment(+5)" in response.execution_log
    assert "Multiply(*2)" in response.execution_log

    # Mixin behaviors executed
    assert "[AUDIT:AuditedBehavior] executed" in response.execution_log
    assert "[METRIC:MetricsBehavior] processed" in response.execution_log
    assert "[AUDIT:CombinedMixinBehavior] started" in response.execution_log
    assert "[METRIC:CombinedMixinBehavior] count" in response.execution_log


# ============================================================================
# Tests: Provider Scopes (Singleton vs Factory)
# ============================================================================


def test_di_singleton_behavior_reused() -> None:
    """Test that singleton behaviors are reused across requests."""

    class CounterHandler(RequestHandler[CounterRequest]):
        def __call__(self, request: CounterRequest) -> CounterResponse:
            return CounterResponse(value=request.value, execution_log=["RequestHandler"])

    class TestContainer(containers.DeclarativeContainer):
        # Singleton - same instance for all requests
        counting = providers.Singleton(CountingBehavior)
        handler = providers.Factory(CounterHandler)

    CountingBehavior.instance_counter = 0  # Reset counter

    container = TestContainer()
    provider = DependencyInjectorServiceProvider(container)
    mediator = Mediator(provider, behaviors=[CountingBehavior])

    # Send 3 requests
    response1 = mediator.send(CounterRequest(value=1))
    response2 = mediator.send(CounterRequest(value=2))
    response3 = mediator.send(CounterRequest(value=3))

    # Should have created only 1 instance
    assert CountingBehavior.instance_counter == 1

    # Should show increasing execution count from same instance
    assert "Counting(inst=1,exec=1)" in response1.execution_log
    assert "Counting(inst=1,exec=2)" in response2.execution_log
    assert "Counting(inst=1,exec=3)" in response3.execution_log


def test_di_factory_behavior_fresh_instances() -> None:
    """Test that factory behaviors create new instances per resolve."""

    class CounterHandler(RequestHandler[CounterRequest]):
        def __call__(self, request: CounterRequest) -> CounterResponse:
            return CounterResponse(value=request.value, execution_log=["RequestHandler"])

    class TestContainer(containers.DeclarativeContainer):
        # Factory - new instance per request
        counting = providers.Factory(CountingBehavior)
        handler = providers.Factory(CounterHandler)

    CountingBehavior.instance_counter = 0  # Reset counter

    container = TestContainer()
    provider = DependencyInjectorServiceProvider(container)
    mediator = Mediator(provider, behaviors=[CountingBehavior])

    # Send 3 requests
    response1 = mediator.send(CounterRequest(value=1))
    response2 = mediator.send(CounterRequest(value=2))
    response3 = mediator.send(CounterRequest(value=3))

    # Discovery does not construct and discard a factory instance.
    assert CountingBehavior.instance_counter == 3

    assert "Counting(inst=1,exec=1)" in response1.execution_log
    assert "Counting(inst=2,exec=1)" in response2.execution_log
    assert "Counting(inst=3,exec=1)" in response3.execution_log


def test_di_mixed_scopes() -> None:
    """Test mixture of singleton and factory behaviors."""

    class CounterHandler(RequestHandler[CounterRequest]):
        def __call__(self, request: CounterRequest) -> CounterResponse:
            return CounterResponse(value=request.value, execution_log=["RequestHandler"])

    class TestContainer(containers.DeclarativeContainer):
        # Singleton - shared across requests
        logging = providers.Singleton(LoggingBehavior, label="shared")
        # Factory - new per request
        increment = providers.Factory(IncrementBehavior, amount=1)
        handler = providers.Factory(CounterHandler)

    container = TestContainer()
    provider = DependencyInjectorServiceProvider(container)
    mediator = Mediator(provider, behaviors=[LoggingBehavior, IncrementBehavior])

    # Get the singleton instance to check call count
    logging_behavior = container.logging()

    # Send multiple requests
    mediator.send(CounterRequest(value=1))
    mediator.send(CounterRequest(value=2))
    mediator.send(CounterRequest(value=3))

    # Singleton should have been called 3 times
    assert logging_behavior.call_count == 3


# ============================================================================
# Tests: Behaviors with Dependencies
# ============================================================================


def test_di_behavior_with_injected_dependency() -> None:
    """Test behavior that has dependencies injected by DI container."""

    class CounterHandler(RequestHandler[CounterRequest]):
        def __call__(self, request: CounterRequest) -> CounterResponse:
            return CounterResponse(value=request.value, execution_log=["RequestHandler"])

    class TestContainer(containers.DeclarativeContainer):
        # Database is a dependency
        database = providers.Singleton(Database)
        # Behavior depends on database
        db_logging = providers.Factory(DatabaseLoggingBehavior, database=database)
        increment = providers.Factory(IncrementBehavior, amount=1)
        handler = providers.Factory(CounterHandler)

    container = TestContainer()
    provider = DependencyInjectorServiceProvider(container)
    mediator = Mediator(provider, behaviors=[DatabaseLoggingBehavior, IncrementBehavior])
    database = container.database()

    # Send requests
    response1 = mediator.send(CounterRequest(value=10))
    response2 = mediator.send(CounterRequest(value=20))

    # Database should have been called twice
    assert database.query_count == 2

    # Responses should show database logging
    assert "DBLog(Logged CounterRequest (total: 1))" in response1.execution_log
    assert "DBLog(Logged CounterRequest (total: 2))" in response2.execution_log


def test_di_behavior_with_shared_dependency() -> None:
    """Test multiple behaviors sharing the same dependency."""

    class CounterHandler(RequestHandler[CounterRequest]):
        def __call__(self, request: CounterRequest) -> CounterResponse:
            return CounterResponse(value=request.value, execution_log=["RequestHandler"])

    class AnotherDBBehavior(PipelineBehavior[CounterRequest]):
        """Another behavior using database."""

        def __init__(self, database: Database) -> None:
            self.database = database

        def __call__(self, request: CounterRequest, next: Any) -> CounterResponse:
            self.database.log_request("BeforeHandler")
            response: CounterResponse = next()
            self.database.log_request("AfterHandler")
            response.execution_log.append("AnotherDB")
            return response

    class TestContainer(containers.DeclarativeContainer):
        database = providers.Singleton(Database)
        db_log1 = providers.Factory(DatabaseLoggingBehavior, database=database)
        db_log2 = providers.Factory(AnotherDBBehavior, database=database)
        handler = providers.Factory(CounterHandler)

    container = TestContainer()
    provider = DependencyInjectorServiceProvider(container)
    mediator = Mediator(provider, behaviors=[DatabaseLoggingBehavior, AnotherDBBehavior])
    database = container.database()

    mediator.send(CounterRequest(value=10))

    # Database should have been queried 3 times (1 + 2)
    assert database.query_count == 3


# ============================================================================
# Tests: Complex Scenarios
# ============================================================================


def test_di_complex_behavior_pipeline() -> None:
    """Test complex pipeline with all behavior types combined."""

    class CounterHandler(RequestHandler[CounterRequest]):
        def __call__(self, request: CounterRequest) -> CounterResponse:
            return CounterResponse(value=request.value, execution_log=["RequestHandler"])

    class ValidationBehavior(PipelineBehavior[CounterRequest]):
        """Validates request."""

        def __call__(self, request: CounterRequest, next: Any) -> CounterResponse:
            if request.value > 1000:
                raise ValueError("Value too large!")
            response: CounterResponse = next()
            response.execution_log.append("Validation")
            return response

    class TestContainer(containers.DeclarativeContainer):
        # Complex pipeline
        validation = providers.Factory(ValidationBehavior)
        short_circuit = providers.Factory(ShortCircuitBehavior)
        conditional = providers.Factory(ConditionalBehavior, threshold=25)
        logging = providers.Singleton(LoggingBehavior, label="audit")
        increment = providers.Factory(IncrementBehavior, amount=10)
        multiply = providers.Factory(MultiplyBehavior, factor=2)
        audited = providers.Factory(AuditedBehavior)
        handler = providers.Factory(CounterHandler)

    container = TestContainer()
    provider = DependencyInjectorServiceProvider(container)
    mediator = Mediator(
        provider,
        behaviors=[
            ValidationBehavior,
            ShortCircuitBehavior,
            ConditionalBehavior,
            LoggingBehavior,
            IncrementBehavior,
            MultiplyBehavior,
            AuditedBehavior,
        ],
    )

    # Normal execution
    response = mediator.send(CounterRequest(value=20))
    assert response.value == 50  # (20 * 2) + 10, conditional not met (checks request.value=20 < 25)
    assert "Validation" in response.execution_log
    assert "ShortCircuit(passed)" in response.execution_log
    assert "Conditional(<25:skip)" in response.execution_log

    # Short-circuit execution
    response = mediator.send(CounterRequest(value=-5))
    assert response.value == -999
    assert response.execution_log == ["ShortCircuit", "Validation"]

    # Validation failure
    with pytest.raises(ValueError, match="Value too large"):
        mediator.send(CounterRequest(value=2000))


def test_di_real_world_scenario() -> None:
    """Test realistic scenario with authentication, logging, caching behaviors."""

    class CounterHandler(RequestHandler[CounterRequest]):
        def __call__(self, request: CounterRequest) -> CounterResponse:
            return CounterResponse(value=request.value, execution_log=["RequestHandler"])

    @dataclass
    class User:
        id: int
        role: str

    class AuthenticationBehavior(PipelineBehavior[CounterRequest]):
        """Checks authentication."""

        def __init__(self, user: User) -> None:
            self.user = user

        def __call__(self, request: CounterRequest, next: Any) -> CounterResponse:
            if self.user.role != "admin":
                raise PermissionError("Admin only!")
            response: CounterResponse = next()
            response.execution_log.append(f"Auth({self.user.role})")
            return response

    class CachingBehavior(PipelineBehavior[CounterRequest]):
        """Caches responses."""

        def __init__(self) -> None:
            self.cache: dict[str, Any] = {}

        def __call__(self, request: CounterRequest, next: Any) -> CounterResponse:
            cache_key = f"request_{request.value}"
            if cache_key in self.cache:
                cached: CounterResponse = self.cache[cache_key]
                cached.execution_log.append("Cache(HIT)")
                return cached

            response: CounterResponse = next()
            response.execution_log.append("Cache(MISS)")
            self.cache[cache_key] = response
            return response

    class TestContainer(containers.DeclarativeContainer):
        user = providers.Singleton(User, id=1, role="admin")
        auth = providers.Factory(AuthenticationBehavior, user=user)
        cache = providers.Singleton(CachingBehavior)
        logging = providers.Factory(LoggingBehavior, label="request")
        increment = providers.Factory(IncrementBehavior, amount=1)
        handler = providers.Factory(CounterHandler)

    container = TestContainer()
    provider = DependencyInjectorServiceProvider(container)
    pipeline = [AuthenticationBehavior, CachingBehavior, LoggingBehavior, IncrementBehavior]
    mediator = Mediator(provider, behaviors=pipeline)

    # First request - cache miss
    response1 = mediator.send(CounterRequest(value=10))
    assert response1.value == 11
    assert "Auth(admin)" in response1.execution_log
    assert "Cache(MISS)" in response1.execution_log

    # Second request with same value - cache hit
    response2 = mediator.send(CounterRequest(value=10))
    assert response2.value == 11
    assert "Cache(HIT)" in response2.execution_log

    # Change user to non-admin
    container.user.override(providers.Singleton(User, id=2, role="user"))
    mediator2 = Mediator(DependencyInjectorServiceProvider(container), behaviors=pipeline)

    with pytest.raises(PermissionError, match="Admin only"):
        mediator2.send(CounterRequest(value=10))


def test_di_error_handling_in_behaviors() -> None:
    """Test error handling and recovery in behaviors."""

    # Use unique request type to avoid handler registration conflict
    @dataclass
    class ErrorTestResponse:
        value: int
        execution_log: list[str]

    @dataclass
    class ErrorTestRequest(Request[ErrorTestResponse]):
        value: int

    class ErrorRecoveryBehavior(PipelineBehavior[ErrorTestRequest]):
        """Recovers from handler errors."""

        def __call__(self, request: ErrorTestRequest, next: Any) -> ErrorTestResponse:
            try:
                result: ErrorTestResponse = next()
                return result
            except ValueError as e:
                return ErrorTestResponse(value=-1, execution_log=[f"Recovered({e})"])

    class FailingHandler(RequestHandler[ErrorTestRequest]):
        """RequestHandler that fails on negative values."""

        def __call__(self, request: ErrorTestRequest) -> ErrorTestResponse:
            if request.value < 0:
                raise ValueError("Negative value!")
            return ErrorTestResponse(value=request.value, execution_log=["RequestHandler"])

    class TestContainer(containers.DeclarativeContainer):
        recovery = providers.Factory(ErrorRecoveryBehavior)
        increment = providers.Factory(IncrementBehavior, amount=1)
        handler = providers.Factory(FailingHandler)

    container = TestContainer()
    provider = DependencyInjectorServiceProvider(container)
    mediator = Mediator(provider, behaviors=[ErrorRecoveryBehavior, IncrementBehavior])

    # Positive value - normal execution
    response = mediator.send(ErrorTestRequest(value=10))
    assert response.value == 10

    # Negative value - recovery
    response = mediator.send(ErrorTestRequest(value=-5))
    assert response.value == -1
    assert "Recovered(Negative value!)" in response.execution_log


# ============================================================================
# Tests: Selective Behavior Application
# ============================================================================


def test_di_behaviors_only_apply_to_matching_requests() -> None:
    """Test that behaviors only apply to their target request types."""

    class CounterHandler(RequestHandler[CounterRequest]):
        def __call__(self, request: CounterRequest) -> CounterResponse:
            return CounterResponse(value=request.value, execution_log=["RequestHandler"])

    class SimpleHandler(RequestHandler[SimpleRequest]):
        def __call__(self, request: SimpleRequest) -> SimpleResponse:
            return SimpleResponse(message=f"Processed: {request.data}")

    class CounterOnlyBehavior(PipelineBehavior[CounterRequest]):
        """Only applies to CounterRequest."""

        def __call__(self, request: CounterRequest, next: Any) -> CounterResponse:
            response: CounterResponse = next()
            response.execution_log.append("CounterOnly")
            return response

    class TestContainer(containers.DeclarativeContainer):
        counter_behavior = providers.Factory(CounterOnlyBehavior)
        counter_handler = providers.Factory(CounterHandler)
        simple_handler = providers.Factory(SimpleHandler)

    container = TestContainer()
    provider = DependencyInjectorServiceProvider(container)
    mediator = Mediator(provider, behaviors=[CounterOnlyBehavior])

    # CounterRequest - behavior applies
    counter_response = mediator.send(CounterRequest(value=10))
    assert "CounterOnly" in counter_response.execution_log

    # SimpleRequest - behavior doesn't apply
    simple_response = mediator.send(SimpleRequest(data="test"))
    assert simple_response.message == "Processed: test"


# ============================================================================
# Tests: Performance and Edge Cases
# ============================================================================


def _make_labeled_logging_behavior(label: str) -> type[PipelineBehavior[CounterRequest]]:
    """Build a distinct LoggingBehavior-shaped class for a given label.

    ``behaviors=`` lists distinct classes and the DI provider's ``get()`` resolves the
    first registered instance of an exact type, so ten providers of the *same* class
    (as in the old registration-order-driven test) would only ever resolve one
    instance. Ten distinct classes are needed to exercise a ten-behavior pipeline.
    """

    class _LabeledLoggingBehavior(PipelineBehavior[CounterRequest]):
        def __call__(self, request: CounterRequest, next: Any) -> CounterResponse:
            response: CounterResponse = next()
            response.execution_log.append(f"Logging({label})")
            return response

    return _LabeledLoggingBehavior


def test_di_many_behaviors() -> None:
    """Test mediator with many behaviors."""

    class CounterHandler(RequestHandler[CounterRequest]):
        def __call__(self, request: CounterRequest) -> CounterResponse:
            return CounterResponse(value=request.value, execution_log=["RequestHandler"])

    behavior_classes = [_make_labeled_logging_behavior(str(i)) for i in range(1, 11)]

    namespace: dict[str, Any] = {
        f"log{i}": providers.Factory(behavior_class)
        for i, behavior_class in enumerate(behavior_classes)
    }
    namespace["handler"] = providers.Factory(CounterHandler)
    TestContainer = type("TestContainer", (containers.DeclarativeContainer,), namespace)

    container = TestContainer()
    provider = DependencyInjectorServiceProvider(container)
    mediator = Mediator(provider, behaviors=behavior_classes)

    response = mediator.send(CounterRequest(value=42))

    # All 10 behaviors should have executed
    assert len([log for log in response.execution_log if log.startswith("Logging")]) == 10
    assert response.value == 42


def test_di_no_behaviors_registered() -> None:
    """Test that mediator works with no behaviors (fast path)."""

    class CounterHandler(RequestHandler[CounterRequest]):
        def __call__(self, request: CounterRequest) -> CounterResponse:
            return CounterResponse(value=request.value, execution_log=["RequestHandler"])

    class TestContainer(containers.DeclarativeContainer):
        handler = providers.Factory(CounterHandler)

    container = TestContainer()
    provider = DependencyInjectorServiceProvider(container)
    mediator = Mediator(provider)

    response = mediator.send(CounterRequest(value=123))

    assert response.value == 123
    assert response.execution_log == ["RequestHandler"]


# ============================================================================
# Tests: behaviors= Validation
# ============================================================================


def test_di_registered_but_unlisted_behavior_does_not_run() -> None:
    """Test that a behavior registered in the DI container but absent from behaviors=
    is not part of the pipeline."""

    class CounterHandler(RequestHandler[CounterRequest]):
        def __call__(self, request: CounterRequest) -> CounterResponse:
            return CounterResponse(value=request.value, execution_log=["RequestHandler"])

    class TestContainer(containers.DeclarativeContainer):
        increment = providers.Factory(IncrementBehavior, amount=5)  # registered...
        handler = providers.Factory(CounterHandler)

    container = TestContainer()
    provider = DependencyInjectorServiceProvider(container)
    mediator = Mediator(provider)  # ...but not listed in behaviors=

    response = mediator.send(CounterRequest(value=10))

    assert response.value == 10
    assert response.execution_log == ["RequestHandler"]


def test_di_mediator_rejects_behavior_not_registered_with_provider() -> None:
    """Test that an unregistered class in behaviors= fails at construction."""

    class CounterHandler(RequestHandler[CounterRequest]):
        def __call__(self, request: CounterRequest) -> CounterResponse:
            return CounterResponse(value=request.value, execution_log=["RequestHandler"])

    class TestContainer(containers.DeclarativeContainer):
        handler = providers.Factory(CounterHandler)

    container = TestContainer()
    provider = DependencyInjectorServiceProvider(container)

    with pytest.raises(InvalidPipelineBehaviorsError, match="not registered"):
        Mediator(provider, behaviors=[IncrementBehavior])


def test_di_mediator_rejects_duplicate_behavior_in_behaviors_list() -> None:
    """Test that a behavior class listed twice in behaviors= fails at construction."""

    class CounterHandler(RequestHandler[CounterRequest]):
        def __call__(self, request: CounterRequest) -> CounterResponse:
            return CounterResponse(value=request.value, execution_log=["RequestHandler"])

    class TestContainer(containers.DeclarativeContainer):
        increment = providers.Factory(IncrementBehavior, amount=5)
        handler = providers.Factory(CounterHandler)

    container = TestContainer()
    provider = DependencyInjectorServiceProvider(container)

    with pytest.raises(InvalidPipelineBehaviorsError, match="more than once"):
        Mediator(provider, behaviors=[IncrementBehavior, IncrementBehavior])


# ============================================================================
# Tests: DependencyInjectorServiceProvider direct API
# ============================================================================


def test_di_provider_get_raises_service_not_found() -> None:
    """DependencyInjectorServiceProvider.get() raises ServiceNotFoundError for an
    unregistered type, listing whatever service types *are* registered."""

    class CounterHandler(RequestHandler[CounterRequest]):
        def __call__(self, request: CounterRequest) -> CounterResponse:
            return CounterResponse(value=request.value, execution_log=["RequestHandler"])

    class TestContainer(containers.DeclarativeContainer):
        handler = providers.Factory(CounterHandler)

    provider = DependencyInjectorServiceProvider(TestContainer())

    with pytest.raises(ServiceNotFoundError) as exc_info:
        provider.get(IncrementBehavior)

    assert exc_info.value.service_type is IncrementBehavior
    assert CounterHandler in exc_info.value.available_types


def test_di_provider_has_and_len() -> None:
    """Exercise has() and __len__() directly on the DI provider."""

    class CounterHandler(RequestHandler[CounterRequest]):
        def __call__(self, request: CounterRequest) -> CounterResponse:
            return CounterResponse(value=request.value, execution_log=["RequestHandler"])

    class TestContainer(containers.DeclarativeContainer):
        increment = providers.Factory(IncrementBehavior, amount=1)
        handler = providers.Factory(CounterHandler)

    provider = DependencyInjectorServiceProvider(TestContainer())

    assert provider.has(CounterHandler) is True
    assert provider.has(IncrementBehavior) is True
    assert provider.has(MultiplyBehavior) is False
    assert len(provider) == 2


def test_di_provider_rejects_non_container() -> None:
    """The public constructor accepts Dependency Injector containers, not lookalikes."""

    class NotAContainer:
        pass

    with pytest.raises(TypeError, match="dependency_injector.containers.Container"):
        DependencyInjectorServiceProvider(NotAContainer())
