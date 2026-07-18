"""Requests implemented as dataclasses with deliberate data semantics.

PyMediate requests do not have to be dataclasses. This example chooses dataclasses and stages
three related decisions: equality and hashing, generated representations, and validation at
construction. These decisions are the same for synchronous and asynchronous requests.
"""

from dataclasses import dataclass, field

from pymediate.sync import Request

# ---- Responses ----


@dataclass(frozen=True)
class Forecast:
    """The answer to a ``GetForecast`` query."""

    city: str
    units: str
    temperature: float
    summary: str


@dataclass(frozen=True)
class Ack:
    """The answer to a ``SubmitReading`` command."""

    station_id: str
    stored: bool


# ---- A frozen query that doubles as its own cache key ----


@dataclass(frozen=True, slots=True)
class GetForecast(Request[Forecast]):
    """Look up the forecast for a city.

    ``frozen=True`` prevents field assignment and allows a generated hash when every compared
    field is hashable. Both fields here are strings, so an instance can be a dictionary key.
    ``slots=True`` removes the per-instance ``__dict__``. ``__post_init__`` normalizes the
    inputs so separate instances for ``"london"`` and ``" LONDON "`` compare equal and have
    the same hash.
    """

    city: str
    units: str = "metric"

    def __post_init__(self) -> None:
        # object.__setattr__ is how you assign on a frozen dataclass: normalize once, here.
        object.__setattr__(self, "city", self.city.strip().title())
        object.__setattr__(self, "units", self.units.strip().lower())
        if not self.city:
            raise ValueError("city must not be empty")
        if self.units not in ("metric", "imperial"):
            raise ValueError(f"units must be 'metric' or 'imperial', got {self.units!r}")


# ---- A mixin that shares a secret field and its validation ----


@dataclass
class Authenticated:
    """Mixin adding an API key omitted from the generated dataclass representation.

    ``field(repr=False)`` affects only the generated ``__repr__``. It is not a general secret
    storage mechanism: explicit logging, serialization, or local-variable capture can still
    expose the value. ``kw_only=True`` makes the field keyword-only.
    """

    api_key: str = field(repr=False, kw_only=True)

    def __post_init__(self) -> None:
        if not self.api_key:
            raise ValueError("api_key must not be empty")


@dataclass
class SubmitReading(Authenticated, Request[Ack]):
    """Record a temperature reading from an authenticated station.

    Mixes in ``Authenticated`` for the hidden ``api_key``, and validates the reading itself.
    Not frozen: it's a one-off command, never a cache key.
    """

    station_id: str
    celsius: float

    def __post_init__(self) -> None:
        super().__post_init__()  # keep the mixin's api_key check
        if not -90.0 <= self.celsius <= 60.0:
            raise ValueError(f"celsius {self.celsius} is outside the plausible range")
