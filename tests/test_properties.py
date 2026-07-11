"""Property-based tests (Hypothesis) for core invariants.

Rather than fixed examples, these tests assert laws that must hold for
generated inputs:

- Services/ServiceProvider: registration order preservation, exact-type
  resolution, provider-as-snapshot immutability
- Mediator round-trips: a handler that echoes its request payload returns it
  unchanged through ``send`` (sync and async)
- Pipeline behaviors: wrap order always matches registration order
"""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

import pymediate
from pymediate.sync import Mediator, PipelineBehavior, Request, RequestHandler, Services

# The autouse `clear_registries` fixture is function-scoped, so Hypothesis flags it:
# it runs once per test, not once per generated example. That is safe here because
# every example that touches the handler registry defines fresh request/handler
# classes, so no state leaks between examples.
relaxed = settings(suppress_health_check=[HealthCheck.function_scoped_fixture])

# Payloads that survive equality round-trips (no floats: NaN != NaN).
payloads = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(),
    st.text(),
    st.lists(st.integers(), max_size=5),
    st.dictionaries(st.text(max_size=5), st.integers(), max_size=5),
)


class IntBox:
    def __init__(self, value: int) -> None:
        self.value = value


class StrBox:
    def __init__(self, value: str) -> None:
        self.value = value


# ==================== Services / ServiceProvider properties ====================


@relaxed
@given(values=st.lists(st.integers(), min_size=1, max_size=10))
def test_get_all_preserves_registration_order(values: list[int]) -> None:
    """get_all returns instances in exact registration order; get returns the first."""
    services = Services()
    for value in values:
        services.add(IntBox(value))
    provider = services.provider()

    assert [box.value for box in provider.get_all(IntBox)] == values
    assert provider.get(IntBox).value == values[0]


@relaxed
@given(ints=st.lists(st.integers(), max_size=5), strs=st.lists(st.text(), max_size=5))
def test_provider_reflects_exactly_what_was_registered(ints: list[int], strs: list[str]) -> None:
    """has/get_all/get_all_types agree with each other and with what was added."""
    services = Services()
    for i in ints:
        services.add(IntBox(i))
    for s in strs:
        services.add(StrBox(s))
    provider = services.provider()

    assert provider.has(IntBox) == bool(ints)
    assert provider.has(StrBox) == bool(strs)
    expected_types = {t for t, added in ((IntBox, ints), (StrBox, strs)) if added}
    assert set(provider.get_all_types()) == expected_types
    assert [box.value for box in provider.get_all(IntBox)] == ints
    assert [box.value for box in provider.get_all(StrBox)] == strs


@relaxed
@given(
    before=st.lists(st.integers(), min_size=1, max_size=5),
    after=st.lists(st.integers(), min_size=1, max_size=5),
)
def test_provider_is_a_snapshot_of_registration_time(before: list[int], after: list[int]) -> None:
    """A built provider is immutable: later Services.add calls don't leak into it."""
    services = Services()
    for value in before:
        services.add(IntBox(value))
    provider = services.provider()
    for value in after:
        services.add(IntBox(value))

    assert [box.value for box in provider.get_all(IntBox)] == before


# ==================== Mediator round-trip properties ====================


@relaxed
@given(payload=payloads)
def test_mediator_send_round_trips_arbitrary_payloads(payload: Any) -> None:
    """An echo handler returns any payload unchanged through Mediator.send."""

    class EchoRequest(Request[object]):
        def __init__(self, payload: object) -> None:
            self.payload = payload

    class EchoHandler(RequestHandler[EchoRequest]):
        def __call__(self, request: EchoRequest) -> object:
            return request.payload

    services = Services()
    services.add(EchoHandler())
    mediator = Mediator(services.provider())

    assert mediator.send(EchoRequest(payload)) == payload


@relaxed
@given(payload=payloads)
def test_async_mediator_send_round_trips_arbitrary_payloads(payload: Any) -> None:
    """An async echo handler returns any payload unchanged through the async Mediator.send."""

    class EchoRequest(Request[object]):
        def __init__(self, payload: object) -> None:
            self.payload = payload

    class EchoHandler(pymediate.RequestHandler[EchoRequest]):
        async def __call__(self, request: EchoRequest) -> object:
            return request.payload

    async def main() -> None:
        services = Services()
        services.add(EchoHandler())
        mediator = pymediate.Mediator(services.provider())

        assert await mediator.send(EchoRequest(payload)) == payload

    asyncio.run(main())


# ==================== Pipeline behavior ordering properties ====================


@relaxed
@given(count=st.integers(min_value=1, max_value=6))
def test_behaviors_wrap_in_registration_order(count: int) -> None:
    """N behaviors always nest in registration order around the handler."""
    log: list[str] = []

    @dataclass
    class OrderResponse:
        value: int

    @dataclass
    class OrderRequest(Request[OrderResponse]):
        value: int

    class OrderHandler(RequestHandler[OrderRequest]):
        def __call__(self, request: OrderRequest) -> OrderResponse:
            log.append("handle")
            return OrderResponse(value=request.value)

    class OrderBehavior(PipelineBehavior[OrderRequest]):
        def __init__(self, index: int) -> None:
            self.index = index

        def __call__(self, request: OrderRequest, next: Callable[[], Any]) -> Any:
            log.append(f"before:{self.index}")
            response = next()
            log.append(f"after:{self.index}")
            return response

    services = Services()
    for index in range(count):
        services.add(OrderBehavior(index))
    services.add(OrderHandler())
    mediator = Mediator(services.provider())

    response = mediator.send(OrderRequest(value=count))

    assert response == OrderResponse(value=count)
    expected = (
        [f"before:{i}" for i in range(count)]
        + ["handle"]
        + [f"after:{i}" for i in reversed(range(count))]
    )
    assert log == expected
