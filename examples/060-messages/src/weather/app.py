"""Run demonstrations of deliberate request-data design."""

import asyncio

from pymediate import Mediator, Services

from .handlers import GetForecastHandler, SubmitReadingHandler, WeatherSource
from .messages import Forecast, GetForecast, SubmitReading


def build_mediator(
    *,
    cache: dict[GetForecast, Forecast] | None = None,
    readings: list[tuple[str, float]] | None = None,
    journal: list[str] | None = None,
) -> Mediator:
    """Wire the two handlers over a shared cache, readings list, and journal.

    Args:
        cache: Forecast cache keyed by the request itself; a fresh dict when omitted.
        readings: List the reading handler appends to; a fresh list when omitted.
        journal: Shared list the handlers append markers to; a new list when omitted.

    Returns:
        A mediator that can route ``GetForecast`` and ``SubmitReading``.
    """
    cache = cache if cache is not None else {}
    readings = readings if readings is not None else []
    journal = journal if journal is not None else []

    services = Services()
    services.add(GetForecastHandler(WeatherSource(), cache, journal))
    services.add(SubmitReadingHandler(readings, journal))
    return Mediator(services.provider())


async def main() -> None:
    """Show equality, generated representations, and construction-time validation."""
    journal: list[str] = []
    mediator = build_mediator(journal=journal)

    # 1. The string fields are hashable. Normalization makes two differently capitalized
    #    instances compare equal, so they address one cache entry.
    await mediator.send(GetForecast("london"))
    await mediator.send(GetForecast("  LONDON "))
    same = GetForecast("london") == GetForecast("LONDON")
    print(f"GetForecast('london') == GetForecast('LONDON'): {same}")
    print(f"Handler journal: {journal}  # miss, then hit")

    # 2. repr=False omits the API key from the generated dataclass representation.
    reading = SubmitReading(station_id="st-1", celsius=21.5, api_key="sk-do-not-log-me")
    print(f"Generated repr: {reading!r}")
    await mediator.send(reading)

    # 3. Bad data fails at construction — the request never reaches a handler.
    try:
        GetForecast("london", units="kelvin")
    except ValueError as exc:
        print(f"Rejected before dispatch: {exc}")


def run() -> None:
    """Console-script entry point (``uv run weather``)."""
    asyncio.run(main())


if __name__ == "__main__":
    run()
