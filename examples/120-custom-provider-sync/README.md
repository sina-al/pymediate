# 120-custom-provider-sync

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/sina-al/pymediate?devcontainer_path=.devcontainer%2F120-custom-provider-sync%2Fdevcontainer.json)

The synchronous mirror of [120-custom-provider](../120-custom-provider/), on
`pymediate.sync`. Same Protocol, same from-scratch adapter over a hand-rolled
`TypeRegistry`, same promise: `ServiceProvider` is a Protocol, and the mediator never
cares which implementation is on the other side of it.

## Run it

```bash
cd examples/120-custom-provider-sync
uv sync
uv run pytest
```

```text
8 passed
```

```console
$ uv run python app.py
2 + 3 = 5
4 * 5 = 20
Logger saw: ['2 + 3 = 5', '4 * 5 = 20']
```

## What changes from the async version

Only the API import and the mechanics — the Protocol, the adapter, and every test
claim are identical:

```python
# app.py
from pymediate.sync import Mediator, Request, RequestHandler, ServiceNotFoundError

class AddHandler(RequestHandler[Add]):
    def __call__(self, request: Add) -> int:       # no async
        result = request.a + request.b
        self._logger.log(f"{request.a} + {request.b} = {result}")
        return result
```

`TypeRegistry` and `TypeRegistryServiceProvider` don't change at all — neither one was
ever async to begin with. Only the handlers and the demo lose `async`/`await`.

## The files

| File | What it is |
| --- | --- |
| [`app.py`](app.py) | **Start here.** `TypeRegistry` (the existing container), `TypeRegistryServiceProvider` (the adapter), and a two-handler demo app. |
| [`test_app.py`](test_app.py) | The five Protocol methods tested in isolation, plus the swap-providers money shot: `uv run pytest` → `8 passed`. |

## Where next

- [120-custom-provider](../120-custom-provider/) — the async default, with the full
  explanation of the Protocol and the adapter.
- [100-dependency-injection-sync](../100-dependency-injection-sync/) — a real DI
  container wrapped the same way, with Factory, Singleton, and `ContextLocalSingleton`
  lifetimes.
- The docs: [dependency injection guide](https://pymediate.sina-al.uk/docs/guide/dependency-injection) ·
  [service provider API reference](https://pymediate.sina-al.uk/docs/api/service-provider).
