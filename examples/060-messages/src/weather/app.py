"""Wire the mediator and run a short demo of the three message-design payoffs."""

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
    """Show frozen-as-cache-key, secret hiding, and validation-at-construction."""
    journal: list[str] = []
    mediator = build_mediator(journal=journal)

    # 1. A frozen request doubles as its own cache key — and normalization means two
    #    differently-typed spellings of the same city collapse to one entry.
    await mediator.send(GetForecast("london"))
    await mediator.send(GetForecast("  LONDON "))
    same = GetForecast("london") == GetForecast("LONDON")
    print(f"GetForecast('london') == GetForecast('LONDON'): {same}")
    print(f"Handler journal: {journal}  # miss, then hit")

    # 2. A secret field stays out of logs: repr omits the api_key entirely.
    reading = SubmitReading(station_id="st-1", celsius=21.5, api_key="sk-do-not-log-me")
    print(f"Logging the request prints: {reading!r}")
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
