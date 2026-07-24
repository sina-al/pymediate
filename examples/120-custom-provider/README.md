# 120-custom-provider

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/sina-al/pymediate?devcontainer_path=.devcontainer%2F120-custom-provider%2Fdevcontainer.json)

`ServiceProvider` is a `Protocol`, so PyMediate does not require the container it ships an
integration for. Any object that answers two questions — "is this type registered?" and "give
me the instance for this type" — can drive a `Mediator`. This example implements those two
methods over [Dishka](https://github.com/reagento/dishka), a container PyMediate has no
built-in support for, and passes the result to `Mediator` unchanged.

It assumes the container-backed wiring from
[100-dependency-injection](../100-dependency-injection/), which uses the supported
`dependency-injector` integration. Read this one when your application already has a container
that PyMediate does not integrate with.

## Run

Run these commands from `examples/120-custom-provider`:

```bash
uv sync
uv run python app.py
```

```text
Python: https://python.org
PyMediate: https://pymediate.sina-al.uk
Audited: ['SaveBookmark', 'SaveBookmark', 'ListBookmarks']
```

Both handlers and the pipeline behavior were resolved from the Dishka container. The audit
entries show the behavior ran on all three dispatches.

## Implement the protocol

The whole integration is two methods:

```python
class DishkaServiceProvider(ServiceProvider):
    def __init__(self, container: Container) -> None:
        self._container = container

    def __getitem__[ServiceT](self, service_type: type[ServiceT]) -> ServiceT:
        if service_type not in self:
            raise ServiceNotFoundError(service_type, self._registered_types())

        return self._container.get(service_type)

    def __contains__(self, service_type: type) -> bool:
        key = DependencyKey(service_type, DEFAULT_COMPONENT)
        return self._container.registry.get_factory(key) is not None
```

`__getitem__` checks before it resolves so a miss raises PyMediate's `ServiceNotFoundError`
rather than Dishka's `NoFactoryError`, keeping callers on the documented exception.

`__contains__` consults the registry instead of calling `container.get()`, because asking
whether a type is registered must not construct the instance. `container.get()` would answer
the question by building the object.

Inheriting from `ServiceProvider` is optional, since the protocol matches structurally. It
makes the intent explicit and lets a type checker confirm both methods are present and
correctly typed. Type information survives: `services[AuditLog]` is an `AuditLog`, not `Any`.

## Read the code

| File | What to read |
| --- | --- |
| [`app.py`](app.py) | **Start here.** Read `DishkaServiceProvider` first, then `build_services` for the container declaration and `build_mediator` for the wiring that never mentions Dishka. |
| [`test_app.py`](test_app.py) | Tests for both protocol methods, including exact-type matching and the check that `__contains__` constructs nothing. |

Run the tests with `uv run pytest`; the expected result is `9 passed`.

## Details

- **Register classes with a no-argument constructor, or supply a factory.** Dishka validates
  the whole dependency graph when the container is built and treats every `__init__` parameter
  as something to inject, including parameters that have defaults. A
  `@dataclass` with `field(default_factory=dict)` is rejected with `GraphMissingFactoryError`;
  `BookmarkStore` and `AuditLog` are therefore plain classes. Requests and responses are
  unaffected because they are never registered with the container.
- **Use Dishka's synchronous `Container`, including on the async API.** `__getitem__` is a
  synchronous method in both PyMediate mirrors, so `AsyncContainer` cannot be adapted to it.
  Handlers still run asynchronously; only their construction is synchronous. The supported
  `dependency-injector` integration has the same constraint and rejects async providers.
- **`__contains__` is not decorative.** The mediator calls it when it is constructed, to reject
  a class listed in `behaviors=` that the provider cannot supply. That is the only place
  PyMediate itself calls it.
- Exact-type matching applies here as everywhere: a registered subclass does not satisfy a
  request for its base class. Dishka's plain `provide()` registers only the type it is given,
  so this holds without extra work — but `WithParents` would register parent types too, which
  would change that.
- The container registers itself, so `dishka.container.Container` appears among the available
  types in a `ServiceNotFoundError` message.

## Where next

- [130-cqrs](../130-cqrs/) — separate write decisions from a projected read model.
- [100-dependency-injection](../100-dependency-injection/) — review the supported
  `dependency-injector` integration this example replaces.
- Read the [ServiceProvider API reference](https://pymediate.sina-al.uk/docs/api/service-provider)
  for the protocol's exact contract.
