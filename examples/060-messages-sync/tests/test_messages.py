"""Tests for the sync message-design example.

The claims under test: (1) a frozen request is hashable and normalized, so it works as a
cache key and equal spellings hit the same entry; (2) a ``repr=False`` field keeps a secret
out of the repr; (3) ``__post_init__`` validation fails at construction, before dispatch.
"""

from collections.abc import Callable
from dataclasses import FrozenInstanceError

import pytest
from pymediate.sync import Mediator

from weather.app import build_mediator
from weather.messages import Forecast, GetForecast, SubmitReading


@pytest.fixture
def journal() -> list[str]:
    return []


@pytest.fixture
def cache() -> dict[GetForecast, Forecast]:
    return {}


@pytest.fixture
def mediator(cache: dict[GetForecast, Forecast], journal: list[str]) -> Mediator:
    return build_mediator(cache=cache, journal=journal)


def test_frozen_request_is_normalized_and_hashable() -> None:
    a = GetForecast("london")
    b = GetForecast("  LONDON ")

    # Normalization collapses the spellings; frozen makes them hashable and equal.
    assert a == b
    assert hash(a) == hash(b)
    assert a.city == "London"
    assert {a: "cached"}[b] == "cached"  # usable as a dict key


def test_frozen_request_cannot_be_mutated() -> None:
    with pytest.raises(FrozenInstanceError):
        GetForecast("london").city = "paris"  # type: ignore[misc]


def test_request_doubles_as_its_own_cache_key(
    mediator: Mediator, cache: dict[GetForecast, Forecast], journal: list[str]
) -> None:
    first = mediator.send(GetForecast("london"))
    second = mediator.send(GetForecast("LONDON"))  # equal after normalization

    assert first == second
    assert journal == ["forecast:miss London", "forecast:hit London"]  # served from cache
    assert len(cache) == 1  # one entry, keyed by the request object itself


def test_secret_field_is_hidden_from_repr() -> None:
    reading = SubmitReading(station_id="st-1", celsius=21.5, api_key="sk-secret")

    text = repr(reading)
    assert "sk-secret" not in text  # the api_key never lands in a log line
    assert "station_id='st-1'" in text  # non-secret fields still show


@pytest.mark.parametrize(
    "factory",
    [
        lambda: GetForecast("london", units="kelvin"),  # bad units
        lambda: GetForecast("   "),  # empty after normalization
        lambda: SubmitReading(station_id="st-1", celsius=999.0, api_key="sk"),  # impossible temp
        lambda: SubmitReading(station_id="st-1", celsius=20.0, api_key=""),  # empty key (mixin)
    ],
)
def test_invalid_requests_fail_at_construction(factory: Callable[[], object]) -> None:
    # The point of __post_init__ validation: bad data raises here, before any dispatch.
    with pytest.raises(ValueError):
        factory()


def test_valid_reading_is_stored(mediator: Mediator) -> None:
    ack = mediator.send(SubmitReading(station_id="st-1", celsius=18.0, api_key="sk-ok"))
    assert ack.stored is True
