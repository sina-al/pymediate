"""The messages — where the interesting decisions live.

A PyMediate request is a plain dataclass, so *how you declare it* is a design choice with
real consequences. This module shows three that pay off:

- ``frozen=True`` makes a request immutable **and hashable**, so a query can be its own
  cache key (see ``GetForecast`` and ``handlers.GetForecastHandler``).
- ``field(repr=False)`` keeps a secret out of every log line and traceback (see the
  ``Authenticated`` mixin's ``api_key``).
- ``__post_init__`` normalizes and validates at construction, so a malformed request
  **fails before it is ever dispatched** — no handler ever sees bad data.

Note: this example is about the *shape* of the message. *Where* validation belongs
architecturally — at the edge as a DTO, or in the core command — is a separate decision,
covered in 065-validation.
"""

from dataclasses import dataclass, field

from pymediate import Request

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

    ``frozen=True`` buys two things at once: the request can't be mutated in flight, and it
    becomes hashable — so a handler can use the request object *itself* as a cache key.
    ``slots=True`` drops the per-instance ``__dict__`` for a lighter object, worth it for a
    high-volume request type. ``__post_init__`` normalizes the inputs (with
    ``object.__setattr__``, since the instance is frozen) so ``"london"`` and ``" LONDON "``
    collapse to the same value — and therefore the same cache key.
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
    """Mixin adding an API key that never appears in a repr, log, or traceback.

    ``field(repr=False)`` hides the value from ``__repr__``; ``kw_only=True`` keeps it out
    of the way of the positional fields on the requests that mix it in. The
    ``__post_init__`` here validates the key, and requests that add their own validation
    call ``super().__post_init__()`` to keep this check.
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
