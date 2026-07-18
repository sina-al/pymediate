# 060-messages-sync

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/sina-al/pymediate?devcontainer_path=.devcontainer%2F060-messages-sync%2Fdevcontainer.json)

PyMediate requests can be ordinary Python classes. This example chooses dataclasses and shows
how their equality, generated representation, and validation rules affect synchronous request
handling.

## Run

From this directory:

```bash
uv sync
uv run weather
```

```text
GetForecast('london') == GetForecast('LONDON'): True
Handler journal: ['forecast:miss London', 'forecast:hit London']  # miss, then hit
Generated repr: SubmitReading(station_id='st-1', celsius=21.5)
Rejected before dispatch: units must be 'metric' or 'imperial', got 'kelvin'
```

The two forecast requests are distinct instances. Normalization gives them equal field values,
so they compare equal and address the same cache entry. The API key is omitted from the generated
representation, and invalid units raise while the request is being constructed.

## Equality and hashing

```python
@dataclass(frozen=True, slots=True)
class GetForecast(Request[Forecast]):
    city: str
    units: str = "metric"

    def __post_init__(self) -> None:
        object.__setattr__(self, "city", self.city.strip().title())
        object.__setattr__(self, "units", self.units.strip().lower())
        if not self.city:
            raise ValueError("city must not be empty")
```

`frozen=True` prevents ordinary field assignment. It also allows the dataclass to generate a
hash when every field used for equality is hashable. Both fields here are strings, so
`GetForecast` can be used as a dictionary key. A frozen dataclass containing a list would still
not be hashable.

The synchronous handler therefore caches by request value:

```python
def __call__(self, request: GetForecast) -> Forecast:
    if request in self._cache:
        return self._cache[request]
    forecast = self._source.lookup(request.city, request.units)
    self._cache[request] = forecast
    return forecast
```

## Generated representations

```python
@dataclass
class Authenticated:
    api_key: str = field(repr=False, kw_only=True)
```

`repr=False` omits `api_key` from the dataclass-generated `repr`. It does not protect the value
from explicit logging, serialization, a debugger, or traceback tools that capture local
variables. Treat the field as sensitive even though the default representation omits it.

## Construction-time validation

`__post_init__` runs after dataclass initialization. `GetForecast` uses it to normalize input and
reject unsupported units. `SubmitReading` calls its mixin's `__post_init__` before checking the
temperature range. This ensures handlers receive only request instances that passed those rules.

The next example separates input-schema validation from business rules; not every validation rule
belongs in a request dataclass.

## Read the code

| File | What to read |
| --- | --- |
| [`src/weather/messages.py`](src/weather/messages.py) | Start here for the request and response dataclasses. |
| [`src/weather/handlers.py`](src/weather/handlers.py) | The cache keyed by `GetForecast`. |
| [`src/weather/app.py`](src/weather/app.py) | Mediator setup and console output. |
| [`tests/test_messages.py`](tests/test_messages.py) | The nine data-semantics tests. |

## Details

`slots=True` removes the per-instance `__dict__`. Use it when its memory and attribute restrictions
fit the application; it is not required by PyMediate. Mutable defaults still require
`field(default_factory=...)` so instances do not share one list or dictionary.

Run `uv run pytest` to execute the nine tests for equality, hashing, representation, and
construction-time errors.

## Where next

- [065-validation-sync](../065-validation-sync/) separates request-body validation from business
  rules with `pymediate.sync`.
- [060-messages](../060-messages/) shows the asynchronous handlers.
- Read the [requests and responses guide](https://pymediate.sina-al.uk/docs/guide/requests-responses).
