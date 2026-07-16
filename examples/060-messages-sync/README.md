# 060-messages-sync

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/sina-al/pymediate?devcontainer_path=.devcontainer%2F060-messages-sync%2Fdevcontainer.json)

The synchronous mirror of [060-messages](../060-messages/), on `pymediate.sync`. Message
design doesn't depend on async — dataclasses are the same everywhere — so this twin is a
near-exact copy with `pymediate.sync` imports and plain (non-`async`) handlers. Same three
payoffs: a `frozen=True` request that doubles as its own **cache key**, a secret hidden with
`field(repr=False)`, and `__post_init__` validation that rejects bad data **at construction**.

## Run it

```bash
cd examples/060-messages-sync
uv sync
uv run weather
```

```text
GetForecast('london') == GetForecast('LONDON'): True
Handler journal: ['forecast:miss London', 'forecast:hit London']  # miss, then hit
Logging the request prints: SubmitReading(station_id='st-1', celsius=21.5)
Rejected before dispatch: units must be 'metric' or 'imperial', got 'kelvin'
```

Two differently-typed spellings of the same city are **equal** (normalization plus `frozen`),
so the second query is a cache **hit**. The logged `SubmitReading` shows no `api_key`. And a
bad `units` value raises the moment the request is constructed — before any handler runs.

## The money shot: a frozen, self-validating request

```python
@dataclass(frozen=True, slots=True)
class GetForecast(Request[Forecast]):
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
```

`frozen=True` makes the request immutable **and hashable**, so the handler caches by the
request object itself: `cache[request] = forecast`. `slots=True` drops the per-instance
`__dict__`. `__post_init__` normalizes and validates at construction. (Only the import
differs from the async twin — `from pymediate.sync import Request`.)

## Keeping secrets out of logs

`field(repr=False)` drops a field from `__repr__`. Here it lives on an `Authenticated`
mixin that shares the field — and its validation — across every request that needs a key:

```python
@dataclass
class Authenticated:
    api_key: str = field(repr=False, kw_only=True)

    def __post_init__(self) -> None:
        if not self.api_key:
            raise ValueError("api_key must not be empty")

print(SubmitReading(station_id="st-1", celsius=21.5, api_key="sk-secret"))
# SubmitReading(station_id='st-1', celsius=21.5)   ← no api_key
```

## The files

| File | What it is |
| --- | --- |
| [`src/weather/messages.py`](src/weather/messages.py) | **Start here.** The frozen `GetForecast`, the `Authenticated` mixin, and `SubmitReading`. |
| [`src/weather/handlers.py`](src/weather/handlers.py) | Thin handlers; `GetForecastHandler` caches by the request object itself. |
| [`src/weather/app.py`](src/weather/app.py) | `build_mediator` and the demo. |
| [`tests/test_messages.py`](tests/test_messages.py) | Asserts hashable/normalized equality, cache-key reuse, secret hiding, and construction-time failure: `uv run pytest` → `9 passed`. |

## Where next

- [060-messages](../060-messages/) — the async original.
- [065-validation](../065-validation/) — edge DTO vs. core command: where validation belongs.
- The docs: [dataclasses guide](https://pymediate.sina-al.uk/docs/guide/dataclasses).
