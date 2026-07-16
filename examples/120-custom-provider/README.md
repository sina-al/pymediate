# 120-custom-provider

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/sina-al/pymediate?devcontainer_path=.devcontainer%2F120-custom-provider%2Fdevcontainer.json)

What if you already have your own container? `ServiceProvider` is a **Protocol**, not a
class you have to inherit from — the mediator resolves handlers through it, and doesn't
care what's on the other side. `Services.provider()` and
`DependencyInjectorServiceProvider` are just two implementations; this example writes a
third, from scratch, over a hand-rolled registry that has nothing to do with PyMediate.

## Run it

```bash
cd examples/120-custom-provider
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

## The Protocol: five methods, any implementation

```python
class ServiceProvider(Protocol):
    def get(self, service_type: type) -> object: ...
    def get_all(self, service_type: type) -> Sequence[object]: ...
    def has(self, service_type: type) -> bool: ...
    def get_all_types(self) -> tuple[type, ...]: ...
    def __len__(self) -> int: ...
```

`TypeRegistryServiceProvider` implements every one of these over `TypeRegistry` — a
name-based registry with no PyMediate awareness at all:

```python
class TypeRegistryServiceProvider:
    def __init__(self, registry: TypeRegistry) -> None:
        self._by_type: dict[type, list[Any]] = {}
        self._order: list[Any] = []
        for instance in registry.all():
            self._by_type.setdefault(type(instance), []).append(instance)
            self._order.append(instance)

    def get(self, service_type: type) -> Any:
        instances = self._by_type.get(service_type)
        if not instances:
            raise ServiceNotFoundError(service_type, list(self._by_type.keys()))
        return instances[0]
```

The whole adapter is: scan the registry once, index by type, answer PyMediate's four
lookup questions plus `__len__` from that index — the same scan-once-and-cache shape
`DependencyInjectorServiceProvider` uses for a real DI container.

## Swap the provider, not the call site

```python
custom_mediator = Mediator(TypeRegistryServiceProvider(build_registry(logger)))

services = Services()
services.add(AddHandler(logger))
hand_wired_mediator = Mediator(services.provider())

# Identical request, identical call site, two completely different ServiceProvider
# implementations underneath. The mediator never notices the difference.
await custom_mediator.send(Add(a=10, b=20))       # -> 30
await hand_wired_mediator.send(Add(a=10, b=20))   # -> 30
```

That's the whole promise, made concrete: `mediator.send(Add(...))` doesn't change,
whichever provider built the mediator.

## The files

| File | What it is |
| --- | --- |
| [`app.py`](app.py) | **Start here.** `TypeRegistry` (the existing container), `TypeRegistryServiceProvider` (the adapter), and a two-handler demo app. |
| [`test_app.py`](test_app.py) | The five Protocol methods tested in isolation, plus the swap-providers money shot: `uv run pytest` → `8 passed`. |

## Small print

- This is the capstone of the curriculum, not a prerequisite for anything — it assumes
  you've already met `Services` (in the earlier examples) and, ideally,
  [100-dependency-injection](../100-dependency-injection/) (a *real* third-party
  container, for contrast).
- `TypeRegistry` is deliberately trivial — the point is the Protocol seam, not the
  container. A real adapter might wrap a lookup service, a plugin registry, or any
  other object graph your application already builds.
- This example doesn't re-teach provider *lifetimes* (Factory vs. Singleton vs.
  scoped) — that's [100-dependency-injection](../100-dependency-injection/). Every
  instance here is a plain, eagerly-built object.

## Where next

- [120-custom-provider-sync](../120-custom-provider-sync/) — the same Protocol and
  adapter on `pymediate.sync`.
- [100-dependency-injection](../100-dependency-injection/) — a real DI container
  wrapped the same way, with Factory, Singleton, and `ContextLocalSingleton` lifetimes.
- The docs: [dependency injection guide](https://pymediate.sina-al.uk/docs/guide/dependency-injection) ·
  [service provider API reference](https://pymediate.sina-al.uk/docs/api/service-provider).
