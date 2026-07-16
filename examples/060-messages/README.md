# 060-messages

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/sina-al/pymediate?devcontainer_path=.devcontainer%2F060-messages%2Fdevcontainer.json)

How should you design your request objects? PyMediate requests are **plain dataclasses**,
so the small declarations on them carry real weight. This example shows three that pay off:
a `frozen=True` request that doubles as its own **cache key**, a secret field kept out of
every log line with `field(repr=False)`, and `__post_init__` validation that rejects bad
data **at construction — before any handler runs**.

## Run it

```bash
cd examples/060-messages
uv sync
uv run weather
```

```text
GetForecast('london') == GetForecast('LONDON'): True
Handler journal: ['forecast:miss London', 'forecast:hit London']  # miss, then hit
Logging the request prints: SubmitReading(station_id='st-1', celsius=21.5)
Rejected before dispatch: units must be 'metric' or 'imperial', got 'kelvin'
```

Line by line: two differently-typed spellings of the same city are **equal** (normalization
plus `frozen` make them the same object *and* the same hash), so the second query is a cache
**hit**. The logged `SubmitReading` shows no `api_key`. And a bad `units` value never reaches
a handler — it raises the moment the request is constructed.

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

- **`frozen=True`** — the request can't be mutated in flight, and it becomes **hashable**,
  so a handler can cache by the request object itself: `cache[request] = forecast`.
- **`slots=True`** — drops the per-instance `__dict__`, a lighter object for a high-volume
  request type.
- **`__post_init__`** — normalizes (`"  LONDON "` → `"London"`, via `object.__setattr__`
  because the instance is frozen) and validates. Invalid input raises here, at construction,
  so no handler ever sees a malformed request.

The handler is thin because the message did the work:

```python
async def __call__(self, request: GetForecast) -> Forecast:
    if request in self._cache:            # the frozen request *is* the key
        return self._cache[request]
    forecast = self._source.lookup(request.city, request.units)
    self._cache[request] = forecast
    return forecast
```

## Keeping secrets out of logs

`field(repr=False)` drops a field from `__repr__`, so it never lands in a log line or
traceback. Here it lives on an `Authenticated` **mixin** that shares the field — and its
validation — across every request that needs a key:

```python
@dataclass
class Authenticated:
    api_key: str = field(repr=False, kw_only=True)

    def __post_init__(self) -> None:
        if not self.api_key:
            raise ValueError("api_key must not be empty")

@dataclass
class SubmitReading(Authenticated, Request[Ack]):
    station_id: str
    celsius: float

    def __post_init__(self) -> None:
        super().__post_init__()           # keep the mixin's api_key check
        if not -90.0 <= self.celsius <= 60.0:
            raise ValueError(f"celsius {self.celsius} is outside the plausible range")

print(SubmitReading(station_id="st-1", celsius=21.5, api_key="sk-secret"))
# SubmitReading(station_id='st-1', celsius=21.5)   ← no api_key
```

## The files

| File | What it is |
| --- | --- |
| [`src/weather/messages.py`](src/weather/messages.py) | **Start here.** The frozen `GetForecast`, the `Authenticated` mixin, and `SubmitReading` — every design decision, with comments. |
| [`src/weather/handlers.py`](src/weather/handlers.py) | Thin handlers; `GetForecastHandler` caches by the request object itself. |
| [`src/weather/app.py`](src/weather/app.py) | `build_mediator` and the demo. |
| [`tests/test_messages.py`](tests/test_messages.py) | Asserts hashable/normalized equality, cache-key reuse, secret hiding, and construction-time failure: `uv run pytest` → `9 passed`. |

## Small print

- **One revelation: message design.** *Where* validation should live — at the edge as a
  DTO, or in the core command — is a different decision, covered next in
  [065-validation](../065-validation/).
- A mutable default like `tags: list[str] = []` is shared across every instance — always use
  `field(default_factory=list)`. See the [dataclasses guide](https://pymediate.sina-al.uk/docs/guide/dataclasses)
  for the full field toolkit (nested value objects, polymorphic hierarchies, and more).

## Where next

- [060-messages-sync](../060-messages-sync/) — the same message design on `pymediate.sync`.
- [065-validation](../065-validation/) — edge DTO vs. core command: where validation belongs.
- The docs: [dataclasses guide](https://pymediate.sina-al.uk/docs/guide/dataclasses).
