"""Handlers — kept deliberately thin, because the lesson is in the messages.

``GetForecastHandler`` is the payoff for ``frozen=True``: it caches responses in a plain
dict keyed by the *request object itself*. That only works because the request is hashable,
which frozen made it. Two equal requests (after normalization) hit the same entry.
"""

from pymediate import RequestHandler

from .messages import Ack, Forecast, GetForecast, SubmitReading


class WeatherSource:
    """A stand-in for a real weather API — deterministic so the demo and tests are stable."""

    def lookup(self, city: str, units: str) -> Forecast:
        """Return a made-up but stable forecast for a city."""
        base_c = 10 + (len(city) % 15)  # arbitrary, deterministic
        temperature = base_c if units == "metric" else round(base_c * 9 / 5 + 32, 1)
        return Forecast(city=city, units=units, temperature=temperature, summary="Partly cloudy")


class GetForecastHandler(RequestHandler[GetForecast]):
    """Answer forecast queries, caching by the frozen request object itself."""

    def __init__(
        self,
        source: WeatherSource,
        cache: dict[GetForecast, Forecast],
        journal: list[str],
    ) -> None:
        self._source = source
        self._cache = cache
        self._journal = journal

    async def __call__(self, request: GetForecast) -> Forecast:
        if request in self._cache:  # the frozen request *is* the key
            self._journal.append(f"forecast:hit {request.city}")
            return self._cache[request]
        self._journal.append(f"forecast:miss {request.city}")
        forecast = self._source.lookup(request.city, request.units)
        self._cache[request] = forecast
        return forecast


class SubmitReadingHandler(RequestHandler[SubmitReading]):
    """Store a station reading. Thin on purpose — the message carried the interesting parts."""

    def __init__(self, readings: list[tuple[str, float]], journal: list[str]) -> None:
        self._readings = readings
        self._journal = journal

    async def __call__(self, request: SubmitReading) -> Ack:
        self._readings.append((request.station_id, request.celsius))
        self._journal.append(f"reading:stored {request.station_id}")
        return Ack(station_id=request.station_id, stored=True)
